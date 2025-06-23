import os
import urllib
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

import pyap
import pytz
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from playwright.async_api import FilePayload
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

from lazer.models import ViolationReport, ViolationSubmission

PPA_SMARTSHEET_URL = os.getenv(
    "PPA_SMARTSHEET_URL",
    "https://app.smartsheet.com/b/form/463e9faa2a644f4fae2a956f331f451c",
)
SUBMIT_SMARTSHEET_URL = os.getenv(
    "SUBMIT_SMARTSHEET_URL",
    "https://forms.smartsheet.com/api/submit/463e9faa2a644f4fae2a956f331f451c",
)


class FinderEnum(StrEnum):
    """Base class for enums that can find the closest match based on a string."""

    @classmethod
    def unknown_value(cls) -> Any:
        raise NotImplementedError(f"{cls.__name__} must implement the unknown_value method.")

    @classmethod
    def find_closest(cls, value: str) -> "FinderEnum":
        """Finds the closest enum member based on the provided value string."""
        value = value.lower()
        for member in cls:
            if value in member.value.lower():
                return member
        return cls.unknown_value()


class ViolationObserved(FinderEnum):
    BIKE_LANE = "Bike Lane (vehicle parked in bike lane)"
    CORNER_CLEARANCE = "Corner Clearance (vehicle parked on corner)"
    CROSSWALK = "Crosswalk (vehicle on crosswalk)"
    HANDICAP_RAMP = "Handicap Ramp (vehicle blocking handicap ramp)"
    SIDEWALK = "Sidewalk"

    @classmethod
    def unknown_value(cls) -> "ViolationObserved":
        """Returns a default value for unknown violations."""
        return cls.BIKE_LANE


class OccurrenceFrequency(FinderEnum):
    NOT_FREQUENTLY = "Not Frequently"
    SOMEWHAT_OFTEN = "Somewhat Often"
    FREQUENTLY = "Frequently"
    UNSURE = "Unsure"

    @classmethod
    def unknown_value(cls) -> "OccurrenceFrequency":
        """Returns a default value for unknown violations."""
        return cls.UNSURE


class VehicleType(FinderEnum):
    COUPE = "Coupe (2 door car)"
    SEDAN = "Sedan (4 door car)"
    PICKUP_TRUCK = "Pickup Truck"
    BOX_TRUCK = "Box-Truck"
    SUV = "SUV"
    MINIVAN = "Minivan"
    VAN = "Van"
    BUS = "Bus"
    MOTORCYCLE = "Motorcycle"
    DIRT_BIKE = "Dirt Bike"
    ATV = "ATV"
    TRACTOR = "Tractor"
    TRAILER = "Trailer"
    TOW_TRUCK = "Tow-Truck"
    FLATBED = "Flatbed"
    CAMPER = "Camper"
    RV = "RV"
    BOAT = "Boat"
    CONSTRUCTION_EQUIPMENT = "Construction Equipment"
    UNKNOWN = "Unknown"

    @classmethod
    def unknown_value(cls) -> "VehicleType":
        """Returns a default value for unknown violations."""
        return cls.UNKNOWN


class VehicleColor(FinderEnum):
    RED = "Red"
    BLUE = "Blue"
    GREEN = "Green"
    YELLOW = "Yellow"
    PURPLE = "Purple"
    PINK = "Pink"
    ORANGE = "Orange"
    BROWN = "Brown"
    BLACK = "Black"
    WHITE = "White"
    GRAY = "Gray"
    GOLD = "Gold"
    SILVER = "Silver"
    TEAL = "Teal"
    MAGENTA = "Magenta"
    VIOLET = "Violet"
    CYAN = "Cyan"
    MAROON = "Maroon"
    BEIGE = "Beige"
    OTHER = "Other"

    @classmethod
    def unknown_value(cls) -> "VehicleColor":
        """Returns a default value for unknown vehicle colors."""
        return cls.OTHER


@dataclass
class MobilityAccessViolation:

    make: str
    body_style: VehicleType | str
    vehicle_color: VehicleColor | str

    violation_observed: ViolationObserved | str

    _date_observed: Optional[str]
    _time_observed: Optional[str]
    _block_number: Optional[str]
    _street_name: Optional[str]
    _zip_code: Optional[str]

    # Parsable fields, optionally provided instead of strings
    parsed_address: Optional[pyap.Address] = field(init=False)
    address: Optional[str]
    date_time_observed: Optional[datetime]

    # optional fields
    occurrence_frequency: OccurrenceFrequency = OccurrenceFrequency.UNSURE
    model: str = ""
    # this field is good to report license plate, since
    # there's no field for it in the form.
    additional_information: str = ""

    def __post_init__(self):
        """Post-initialization to parse the address."""
        if not all([self._block_number, self._street_name, self._zip_code]) or self.address:
            raise ValueError("Must supply all address parts or an address to parse")
        self.parsed_address = None
        if self.address:
            parsed_addresses = pyap.parse(self.address, country="US")
            if (
                len(parsed_addresses) != 1
                or parsed_addresses[0].street_name is None
                or parsed_addresses[0].street_type is None
                or parsed_addresses[0].postal_code is None
            ):
                raise ValueError(f"address could not be parsed: {self.address}")
            self.parsed_address = parsed_addresses[0]

        if not all([self._date_observed, self._time_observed]) or self.date_time_observed:
            raise ValueError("Must supply all date/time observed parts or a datetime to parse")
        if self.date_time_observed:
            # convert to est
            est = pytz.timezone("US/Eastern")
            self.date_time_observed = self.date_time_observed.astimezone(est)

        # ensure all enum fields are of the correct type
        fields: list[str, FinderEnum] = [
            ("body_style", VehicleType),
            ("vehicle_color", VehicleColor),
            ("violation_observed", ViolationObserved),
            ("occurrence_frequency", OccurrenceFrequency),
        ]

        for field_name, field_type in fields:
            field_value = getattr(self, field_name)
            if not isinstance(field_value, field_type):
                closest_value = field_type.find_closest(field_value)
                setattr(self, field_name, closest_value)

    # street name here is a dropdown, not a free form.
    # block_number: int
    # street_name: str
    # example address: Wharton Square Park, 2300 Wharton St, Philadelphia, PA 19146, USA
    @property
    def block_number(self) -> int:
        """Returns the block number from the address."""
        if self._block_number:
            return self._block_number
        return self.parsed_address.street_number  # type: ignore

    @property
    def street_name(self) -> str:
        """Returns the street name from the address."""
        if self._street_name:
            return self._street_name
        return (
            self.parsed_address.street_name.upper()  # type: ignore
            + " "
            + self.parsed_address.street_type.upper()  # type: ignore
        )

    @property
    def zip_code(self) -> str:
        """Returns the zip code from the address."""
        if self._zip_code:
            return self._zip_code
        return self.parsed_address.postal_code  # type: ignore

    @property
    def date_observed(self) -> str:
        """Returns the date part of the observed datetime."""
        if self._date_observed:
            return self._date_observed
        return self.date_time_observed.strftime("%m/%d/%Y")

    @property
    def time_observed(self) -> str:
        """Returns the time part of the observed datetime."""
        if self._time_observed:
            return self._time_observed
        # Return the time in EST (should this be 24 hour format?)
        return self.date_time_observed.strftime("%I:%M %p")

    @classmethod
    def from_json(cls, data: dict) -> "MobilityAccessViolation":
        """Creates a MobilityAccessViolation instance from a JSON-like dictionary."""
        vehicle = data.get("vehicle", {})
        if not vehicle:
            # see if there is an array
            vehicles = data.get("vehicles", [])
            if vehicles:
                vehicle = vehicles[0]
            else:
                raise ValueError("Vehicle data is required to create a MobilityAccessViolation.")
        if "timestamp" not in data or "address" not in data:
            raise ValueError("Timestamp and address are required fields.")
        plate = vehicle.get("plate", {}).get("props", {}).get("plate", {})[0].get("value", "")
        region = vehicle.get("plate", {}).get("props", {}).get("region", {})[0].get("value", "")
        # override to make it easier
        vehicle = vehicle.get("vehicle", {})

        vehicle_type = vehicle.get("type", "")
        body_style = VehicleType.find_closest(vehicle_type)

        props = vehicle.get("props")

        make_model = props.get("make_model", {})[0]
        make = make_model.get("make", "")
        model = make_model.get("model", "")
        color = props.get("color", "")[0].get("value", "")
        vehicle_color = VehicleColor.find_closest(color)

        return cls(
            date_time_observed=datetime.fromisoformat(data["timestamp"]),
            make=make,
            model=model,
            body_style=body_style,
            vehicle_color=vehicle_color,
            additional_information=f"License Plate: {plate} ({region})",
            # not sure which one to select here...
            violation_observed=ViolationObserved.BIKE_LANE,  # type: ignore
            address=data["address"],
            # picture=data.get("picture", ""),
        )


async def submit_form_with_playwright(
    submission: ViolationSubmission,
    violation: MobilityAccessViolation,
    photo: str | ContentFile,
    send_copy_to_email: str | None = None,
    tracing: bool = False,
    screenshot_dir: str | None = None,
    violation_report: ViolationReport | None = None,
) -> None:
    """Method to submit a violation to the PPA's Smartsheet using Playwright.

    Args:
        violation (MobilityAccessViolation): The description of the violation to submit.
    """
    # smartsheet allows pre-filling of fields using query parameters.
    # for example, date observed would be Date%20Observed=06/03/2025

    if violation_report is None:
        violation_report = ViolationReport(
            submission=submission,
            date_observed=violation.date_observed,
            time_observed=violation.time_observed,
            make=violation.make,
            model=violation.model,
            body_style=violation.body_style,
            vehicle_color=violation.vehicle_color,
            violation_observed=violation.violation_observed,
            occurrence_frequency=violation.occurrence_frequency,
            block_number=violation.block_number,
            street_name=violation.street_name,
            zip_code=violation.zip_code,
            additional_information=violation.additional_information,
        )

    if isinstance(photo, str):
        if not os.path.exists(photo):
            raise FileNotFoundError(f"Photo file not found: {photo}")
        with open(photo, "rb") as f:
            photo = ContentFile(f.read(), name=os.path.basename(photo))
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not tracing)
        context = await browser.new_context(viewport={"width": 1024, "height": 3000})

        if tracing:
            tracing_debug_key = os.urandom(3).hex()
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = await context.new_page()
        await stealth_async(page)

        # Construct the URL with query parameters
        params = {
            "Date Observed": violation.date_observed,
            "Time Observed": violation.time_observed,
            "Make": violation.make,
            "Model": violation.model,
            "Body Style": violation.body_style,
            "Vehicle Color": violation.vehicle_color,
            "Violation Observed": violation.violation_observed,
            "Block Number": violation.block_number,
            "Street Name": violation.street_name,
            "Zip Code": violation.zip_code,
            "How frequently does this occur?": violation.occurrence_frequency,
            "Additional Information": violation.additional_information,
            # not sure how to do "send me a copy of my responses"
        }
        url_parts = urllib.parse.urlparse(PPA_SMARTSHEET_URL)
        query = dict(urllib.parse.parse_qsl(url_parts.query))
        query.update(params)  # type: ignore

        full_url = url_parts._replace(query=urllib.parse.urlencode(query)).geturl()
        await page.goto(full_url)
        # wait for the form to load
        await page.wait_for_load_state("networkidle")

        # click the file chooser
        async with page.expect_file_chooser() as fc_info:
            await page.get_by_text("browse").click()
        file_chooser = await fc_info.value
        if isinstance(photo, str):
            await file_chooser.set_files(photo)
        elif isinstance(photo, ContentFile):
            upload = FilePayload(
                name=getattr(photo, "name", "violation_photo.jpg"),
                mimeType="image/jpeg",
                buffer=photo.read(),  # limit how much we read?
            )

            await file_chooser.set_files(upload)

        # TODO: We cannot do an email confirmation since it _always_
        # requires recaptcha :(
        # if send_copy_to_email:
        if False:
            # find a checkbox with name property "EMAIL_RECEIPT_CHECKBOX"
            await page.locator("[name='EMAIL_RECEIPT_CHECKBOX']").check()
            # fill the field with name property "EMAIL_RECEIPT"
            await page.locator("[name='EMAIL_RECEIPT']").fill(send_copy_to_email)

        # submit the form
        try:
            if screenshot_dir:
                await page.screenshot(
                    path=f"{screenshot_dir}/screenshot-before-submit.png", full_page=True
                )
                with open(f"{screenshot_dir}/screenshot-before-submit.png", "rb") as f:
                    violation_report.screenshot_before_submit.save(
                        "screenshot-before-submit.png", f, save=False
                    )

            if not settings.DEBUG and violation_report.submission.created_by.email not in (
                "playstore@bikeaction.org",
                "appstore@bikeaction.org",
            ):
                async with page.expect_request(
                    lambda request: request.url == SUBMIT_SMARTSHEET_URL
                    and request.method.lower() == "post"
                ) as _:
                    await page.click('button:text("Submit")')

            if screenshot_dir:
                await page.screenshot(
                    path=f"{screenshot_dir}/screenshot-after-submit.png", full_page=True
                )
                with open(f"{screenshot_dir}/screenshot-after-submit.png", "rb") as f:
                    violation_report.screenshot_after_submit.save(
                        "screenshot-after-submit.png", f, save=False
                    )

            # make sure there is a POST to the form URL and it returned 200
            # also, the submission page should have an h1 element with specific
            await page.wait_for_load_state("networkidle")
            if not settings.DEBUG and violation_report.submission.created_by.email not in (
                "playstore@bikeaction.org",
                "appstore@bikeaction.org",
            ):
                # validate the submission page
                success_text = page.get_by_role(
                    "heading",
                    name="Filling out the mobility access violation reporting form "
                    "may not result in immediate enforcement action",
                )
                await success_text.wait_for(state="visible", timeout=10000)
            if screenshot_dir:
                await page.screenshot(
                    path=f"{screenshot_dir}/screenshot-success.png", full_page=True
                )
                with open(f"{screenshot_dir}/screenshot-success.png", "rb") as f:
                    violation_report.screenshot_success.save(
                        "screenshot-success.png", f, save=False
                    )
            violation_report.submitted = timezone.now()

        except PlaywrightTimeoutError:
            if screenshot_dir:
                await page.screenshot(
                    path=f"{screenshot_dir}/screenshot-error.png", full_page=True
                )
                with open(f"{screenshot_dir}/screenshot-error.png", "rb") as f:
                    violation_report.screenshot_error.save("screenshot-error.png", f, save=False)
            if tracing:
                await context.tracing.stop(path=f"tracing_{tracing_debug_key}.zip")
            await context.close()
            await browser.close()
            return violation_report

        if tracing:
            await context.tracing.stop(path=f"tracing_{tracing_debug_key}.zip")
        if screenshot_dir:
            await page.screenshot(path=f"{screenshot_dir}/screenshot-final.png", full_page=True)
            with open(f"{screenshot_dir}/screenshot-final.png", "rb") as f:
                violation_report.screenshot_final.save("screenshot-final.png", f, save=False)
        await context.close()
        await browser.close()
        return violation_report
