import json
import re
from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.contrib.admin.widgets import AdminTextInputWidget
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos.error import GEOSException


class GeoJSONField(forms.JSONField):
    def prepare_value(self, value):
        return "" if value is None else super().prepare_value(value)


class ReportAreaForm(forms.Form):
    filter_mode = forms.ChoiceField(
        label="Area type", choices=[("street", "Street and blocks"), ("geojson", "GeoJSON area")]
    )
    street_name = forms.CharField(
        required=False,
        max_length=200,
        help_text="Matches part of a street name, e.g. S 13TH ST.",
        widget=AdminTextInputWidget,
    )
    block_range = forms.CharField(
        required=False,
        max_length=30,
        widget=AdminTextInputWidget,
        help_text="Optional: a single block (100) or an inclusive range (100-300).",
    )
    geojson = GeoJSONField(
        label="GeoJSON",
        required=False,
        widget=forms.Textarea(attrs={"rows": 8, "cols": 60, "class": "vLargeTextField"}),
        help_text="Paste a Polygon, MultiPolygon, Feature, or FeatureCollection with one feature.",
    )

    def clean(self):
        data = super().clean()
        self.polygon = None
        if data.get("filter_mode") == "street":
            if not data.get("street_name"):
                self.add_error("street_name", "Enter a street name.")
            block_range = data.get("block_range", "")
            if block_range:
                if not re.fullmatch(r"\d+(?:\s*-\s*\d+)?", block_range):
                    self.add_error("block_range", "Enter a block number or range, such as 100-300.")
                elif "-" in block_range:
                    low, high = map(int, block_range.split("-"))
                    if low > high:
                        self.add_error(
                            "block_range", "The first block must be no larger than the last."
                        )
            data["geojson"] = None
        elif data.get("filter_mode") == "geojson":
            geometry = data.get("geojson")
            try:
                if geometry["type"] == "FeatureCollection":
                    if len(geometry["features"]) != 1:
                        raise ValueError
                    geometry = geometry["features"][0]
                if geometry["type"] == "Feature":
                    geometry = geometry["geometry"]
                if geometry["type"] not in ("Polygon", "MultiPolygon"):
                    raise ValueError
                polygon = GEOSGeometry(json.dumps(geometry), srid=4326)
                if polygon.empty or not polygon.valid:
                    raise ValueError
                self.polygon = polygon
            except (TypeError, KeyError, IndexError, ValueError, GEOSException):
                self.add_error(
                    "geojson", "Enter a valid Polygon or MultiPolygon in GeoJSON format."
                )
            data["street_name"] = ""
            data["block_range"] = ""
        return data


class ReportComparisonForm(forms.Form):
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional. Include violations captured on or after this date.",
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional. Include violations through the end of this date.",
    )
    comparison_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional. Compare violations before this date with those on or after it.",
    )
    timezone = forms.CharField(
        initial="America/New_York",
        widget=AdminTextInputWidget,
        help_text="Timezone for the date range and comparison date, e.g. America/New_York.",
    )

    def clean(self):
        data = super().clean()
        start = data.get("start_date")
        end = data.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "The end date must be on or after the start date.")
        if end and end.year == 9999:
            self.add_error("end_date", "Enter an end date before the year 9999.")
        return data

    def clean_timezone(self):
        value = self.cleaned_data["timezone"]
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError("Enter a valid timezone, e.g. America/New_York.")
        return value

    def comparison_datetime(self):
        date = self.cleaned_data.get("comparison_date")
        if date:
            return datetime.combine(date, time.min, tzinfo=ZoneInfo(self.cleaned_data["timezone"]))
        return None
