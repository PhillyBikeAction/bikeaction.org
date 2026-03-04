import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

import pyap
import pytz


class FinderEnum(StrEnum):
    """Base class for enums that can find the closest match based on a string."""

    @classmethod
    def unknown_value(cls) -> Any:
        raise NotImplementedError(f"{cls.__name__} must implement the unknown_value method.")

    @classmethod
    def get_legacy_mappings(cls) -> dict[str, str]:
        """Return legacy mappings for this enum. Override in subclasses if needed."""
        return {}

    @classmethod
    def find_closest(cls, value: str) -> "FinderEnum":
        """Finds the closest enum member based on the provided value string.

        First checks legacy mappings for exact matches (case-insensitive),
        then tries substring matching against current enum values.
        """
        value_lower = value.lower()

        # Check legacy mappings first (for backlog reports from old Smartsheet form)
        legacy_mappings = cls.get_legacy_mappings()
        if legacy_mappings:
            for legacy_key, new_value in legacy_mappings.items():
                if legacy_key.lower() == value_lower:
                    logging.info(
                        f"Mapping legacy value '{value}' to '{new_value}' for {cls.__name__}"
                    )
                    # Find and return the enum member with this value
                    for member in cls:
                        if member.value == new_value:
                            return member

        # Fall back to substring matching
        for member in cls:
            if value_lower in member.value.lower():
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
    SUV = "SUV"
    MINIVAN = "Minivan"
    VAN = "Van"
    PICKUP_TRUCK = "Pickup Truck"
    BOX_TRUCK = "Box-Truck"
    BUS = "Bus"
    BOAT = "Boat"
    RV = "RV"
    MOTORCYCLE = "Motorcycle"
    ATV = "ATV"
    TRACTOR = "Tractor"
    TRAILER = "Trailer"
    CAMPER = "Camper"
    CONSTRUCTION_EQUIPMENT = "Construction Equipment"
    FLATBED = "Flatbed"
    TOW_TRUCK = "Tow-Truck"
    UNKNOWN = "Unknown"

    @classmethod
    def get_legacy_mappings(cls) -> dict[str, str]:
        """Legacy mappings from old Smartsheet form to new PowerApps form."""
        return {
            "Dirt Bike": "Motorcycle",  # Old form had "Dirt Bike", map to closest equivalent
        }

    @classmethod
    def unknown_value(cls) -> "VehicleType":
        """Returns a default value for unknown violations."""
        return cls.UNKNOWN


class VehicleColor(FinderEnum):
    BEIGE = "Beige"
    BLACK = "Black"
    BLUE = "Blue"
    BROWN = "Brown"
    GOLD = "Gold"
    GRAY = "Gray"
    GREEN = "Green"
    MAROON = "Maroon"
    OTHER = "Other"
    PINK = "Pink"
    PURPLE = "Purple"
    RED = "Red"
    SILVER = "Silver"
    TEAL = "Teal"
    WHITE = "White"

    @classmethod
    def get_legacy_mappings(cls) -> dict[str, str]:
        """Legacy mappings from old Smartsheet form to new PowerApps form."""
        return {
            "Yellow": "Gold",  # Closest color match
            "Orange": "Red",  # Map to closest available color
            "Magenta": "Pink",  # Magenta is similar to pink
            "Violet": "Purple",  # Violet is a shade of purple
            "Cyan": "Teal",  # Cyan and teal are in the same color family
        }

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
