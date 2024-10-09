from django.contrib.contenttypes.admin import GenericTabularInline

from django.contrib.gis import admin
from django.contrib.gis.db import models
from django.contrib.gis.forms.widgets import OSMWidget

from facets.models import (
    Custom,
    District,
    RegisteredCommunityOrganization,
    StateHouseDistrict,
    StateSenateDistrict,
    ZipCode,
)


class DistrictAdmin(admin.ModelAdmin):
    list_display = ["name"]

    formfield_overrides = {
        models.MultiPolygonField: {"widget": OSMWidget},
    }


class RegisteredCommunityOrganizationAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    readonly_fields = ("zip_code_names", "zip_codes")

    formfield_overrides = {
        models.MultiPolygonField: {"widget": OSMWidget},
        ZipCode: {"widget": OSMWidget},
    }

    def zip_code_names(self, obj):
        return ", ".join(
            [
                z.name
                for z in obj.intersecting_zips.all()
                if z.mpoly.intersection(obj.mpoly).area / z.mpoly.area > 0.01
            ]
        )

    def zip_codes(self, obj):
        return obj.intersecting_zips.all()


class ZipCodeAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]

    formfield_overrides = {
        models.MultiPolygonField: {"widget": OSMWidget},
    }


class StateHouseDistrictAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    formfield_overrides = {
        models.MultiPolygonField: {"widget": OSMWidget},
    }


class StateSenateDistrictAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    formfield_overrides = {
        models.MultiPolygonField: {"widget": OSMWidget},
    }


class CustomAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    readonly_fields = ["profiles"]
    formfield_overrides = {
        models.MultiPolygonField: {
            "widget": OSMWidget(
                attrs={"default_lat": 39.9526, "default_lon": -75.1652, "default_zoom": 10}
            )
        },
    }

    @admin.display(description="Profiles")
    def profiles(self, obj=None):
        if obj is None:
            return []
        return list(obj.contained_profiles.all())


admin.site.register(District, DistrictAdmin)
admin.site.register(RegisteredCommunityOrganization, RegisteredCommunityOrganizationAdmin)
admin.site.register(ZipCode, ZipCodeAdmin)
admin.site.register(StateHouseDistrict, StateHouseDistrictAdmin)
admin.site.register(StateSenateDistrict, StateSenateDistrictAdmin)
admin.site.register(Custom, CustomAdmin)
