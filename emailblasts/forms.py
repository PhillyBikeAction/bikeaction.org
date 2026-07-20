import json
import re

from django import forms
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from campaigns.models import Petition
from emailblasts.models import EmailBlastTargetNode
from emailblasts.utils import email_blast_full_body
from events.models import ScheduledEvent
from facets.models import District, Division, RegisteredCommunityOrganization, Ward, ZipCode
from pbaabp.email import template_from_string


class EmailDraftForm(forms.Form):
    TARGET_FIELD_BY_TYPE = {
        EmailBlastTargetNode.TargetType.DISTRICT: "district",
        EmailBlastTargetNode.TargetType.RCO: "rco",
        EmailBlastTargetNode.TargetType.ZIP_CODE: "zip_code",
        EmailBlastTargetNode.TargetType.WARD: "ward",
        EmailBlastTargetNode.TargetType.DIVISION: "division",
        EmailBlastTargetNode.TargetType.GEOJSON: "geojson",
        EmailBlastTargetNode.TargetType.PETITION: "petition",
        EmailBlastTargetNode.TargetType.EVENT_RSVP: "event_rsvp",
        EmailBlastTargetNode.TargetType.EVENT_SIGNIN: "event_signin",
    }
    MODEL_BY_TARGET_FIELD = {
        "district": District,
        "rco": RegisteredCommunityOrganization,
        "zip_code": ZipCode,
        "ward": Ward,
        "division": Division,
        "petition": Petition,
        "event_rsvp": ScheduledEvent,
        "event_signin": ScheduledEvent,
    }

    subject = forms.CharField(
        required=True,
        label=_("Subject"),
        widget=forms.TextInput(
            attrs={
                "placeholder": "Email subject",
                "autocomplete": "off",
                "autocorrect": "off",
                "autocapitalize": "off",
                "spellcheck": "false",
            }
        ),
    )
    reply_to = forms.EmailField(
        required=True,
        label=_("Reply-To"),
        widget=forms.EmailInput(
            attrs={
                "placeholder": "organizer@bikeaction.org",
                "autocomplete": "email",
            }
        ),
    )
    target_name = forms.CharField(
        required=True,
        label=_("Target name"),
        widget=forms.TextInput(attrs={"placeholder": "Short internal name for this audience"}),
    )
    target_description = forms.CharField(
        required=True,
        label=_("Recipient reason"),
        widget=forms.Textarea(
            attrs={
                "placeholder": "live near the proposed safety improvements",
                "rows": 3,
            }
        ),
    )
    target_operator = forms.ChoiceField(
        required=True,
        label=_("Target matching"),
        choices=EmailBlastTargetNode.Operator.choices,
        initial=EmailBlastTargetNode.Operator.OR,
    )
    body = forms.CharField(
        required=True,
        label=_("Message body (Markdown)"),
        widget=forms.Textarea(
            attrs={
                "placeholder": "Write the main message. Greeting, recipient reason, and signoff are added automatically.",
                "rows": 15,
                "autocomplete": "off",
                "autocorrect": "off",
                "autocapitalize": "off",
                "spellcheck": "false",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_choices = {
            "district": self._model_choices(District.objects.all(), key=self._facet_number),
            "rco": self._model_choices(
                RegisteredCommunityOrganization.objects.all(), key=lambda facet: facet.name
            ),
            "zip_code": self._model_choices(ZipCode.objects.all(), key=lambda facet: facet.name),
            "ward": self._model_choices(Ward.objects.all(), key=self._facet_number),
            "division": self._model_choices(
                Division.objects.select_related("ward"), key=self._division_sort_key
            ),
            "petition": self._model_choices(
                Petition.objects.all(), key=lambda petition: petition.title
            ),
            "event_rsvp": self._model_choices(
                ScheduledEvent.objects.all(), key=lambda event: event.start_datetime
            ),
            "event_signin": self._model_choices(
                ScheduledEvent.objects.all(), key=lambda event: event.start_datetime
            ),
        }
        self.cleaned_target_rows = []

    def _model_choices(self, queryset, key):
        return [(str(obj.pk), str(obj)) for obj in sorted(queryset, key=key)]

    def _facet_number(self, facet):
        for key in ("district_number", "ward_num", "ward_number"):
            value = facet.properties.get(key)
            if value is not None:
                return int(value)
        match = re.search(r"\d+", facet.name)
        return int(match.group()) if match else 0

    def _division_sort_key(self, division):
        division_num = division.properties.get("DIVISION_NUM", "")
        if division_num:
            return int(division_num[:2]), int(division_num[2:])
        numbers = [int(number) for number in re.findall(r"\d+", division.name)]
        return tuple(numbers) if numbers else (0, 0)

    def clean(self):
        cleaned_data = super().clean()
        self.cleaned_target_rows = self.clean_target_rows()

        if not self.cleaned_target_rows:
            raise ValidationError(_("Select at least one target."))

        body = cleaned_data.get("body")
        target_description = cleaned_data.get("target_description")
        if body and target_description:
            try:
                template_from_string(email_blast_full_body(body, target_description))
            except Exception as error:
                raise ValidationError(
                    _("Fix the Django template syntax in the message body or recipient reason.")
                ) from error

        cleaned_data["target_rows"] = self.cleaned_target_rows
        return cleaned_data

    def clean_target_rows(self):
        rows = []
        errors = []
        seen_indexes = self.target_row_indexes()

        for index in seen_indexes:
            target_type = self.data.get(f"target_type_{index}", "")
            target_id = self.data.get(f"target_value_{index}", "")
            target_geojson = self.data.get(f"target_geojson_{index}", "")

            if not target_type and not target_id and not target_geojson:
                continue

            try:
                rows.append(self.clean_target_row(index, target_type, target_id, target_geojson))
            except ValidationError as error:
                errors.extend(error.messages)

        if errors:
            raise ValidationError(errors)
        if any(row["target_type"] == EmailBlastTargetNode.TargetType.ALL_PROFILES for row in rows):
            return [
                {
                    "target_type": EmailBlastTargetNode.TargetType.ALL_PROFILES,
                    "target_id": "",
                    "target_name": EmailBlastTargetNode.TargetType.ALL_PROFILES.label,
                    "target_geojson": None,
                }
            ]
        return rows

    def target_row_indexes(self):
        indexes = set()
        for key in self.data.keys():
            match = re.match(r"target_type_(\d+)$", key)
            if match:
                indexes.add(int(match.group(1)))
        return sorted(indexes)

    def clean_target_row(self, index, target_type, target_id, target_geojson):
        valid_target_types = {choice[0] for choice in self.target_type_choices()}
        if target_type not in valid_target_types:
            raise ValidationError(_(f"Target {index + 1}: select a target type."))

        if target_type == EmailBlastTargetNode.TargetType.ALL_PROFILES:
            return {
                "target_type": target_type,
                "target_id": "",
                "target_name": EmailBlastTargetNode.TargetType.ALL_PROFILES.label,
                "target_geojson": None,
            }

        if target_type == EmailBlastTargetNode.TargetType.GEOJSON:
            if not target_geojson:
                raise ValidationError(_(f"Target {index + 1}: paste a GeoJSON boundary."))
            return {
                "target_type": target_type,
                "target_id": "",
                "target_name": "GeoJSON boundary",
                "target_geojson": self.clean_geojson_boundary(target_geojson),
            }

        field_name = self.TARGET_FIELD_BY_TYPE[target_type]
        model = self.MODEL_BY_TARGET_FIELD[field_name]
        target = model.objects.filter(pk=target_id).first()
        if target is None:
            raise ValidationError(_(f"Target {index + 1}: select a target."))

        return {
            "target_type": target_type,
            "target_id": str(target.pk),
            "target_name": str(target),
            "target_geojson": None,
        }

    def target_type_choices(self):
        return [
            choice
            for choice in EmailBlastTargetNode.TargetType.choices
            if choice[0] != EmailBlastTargetNode.TargetType.LEGACY
        ]

    def clean_geojson_boundary(self, value):
        try:
            data = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValidationError(_("Enter valid GeoJSON.")) from error

        try:
            geometry = self.geojson_geometry(data)
            geom = GEOSGeometry(json.dumps(geometry))
        except Exception as error:
            raise ValidationError(_("Enter a valid GeoJSON boundary.")) from error

        if geom.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValidationError(
                _("GeoJSON boundary must be a Polygon, MultiPolygon, or LineString.")
            )

        return data

    def geojson_geometry(self, data):
        if data.get("type") == "FeatureCollection":
            polygons = []

            for feature in data.get("features") or []:
                geometry = self.geojson_geometry(feature)
                if geometry.get("type") == "Polygon":
                    polygons.append(geometry.get("coordinates"))
                elif geometry.get("type") == "MultiPolygon":
                    polygons.extend(geometry.get("coordinates"))
                elif geometry.get("type") == "LineString":
                    polygons.append(self.linestring_to_polygon_coordinates(geometry))
                else:
                    raise ValidationError(_("GeoJSON boundary must contain polygons."))

            return {"type": "MultiPolygon", "coordinates": polygons}

        if data.get("type") == "Feature":
            data = data.get("geometry") or {}

        if data.get("type") == "LineString":
            data = {
                "type": "Polygon",
                "coordinates": self.linestring_to_polygon_coordinates(data),
            }

        return data

    def linestring_to_polygon_coordinates(self, geometry):
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 3:
            raise ValidationError(_("GeoJSON LineString boundary must have at least three points."))
        if coordinates[0] != coordinates[-1]:
            coordinates = [*coordinates, coordinates[0]]
        return [coordinates]
