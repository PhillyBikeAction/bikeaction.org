from django.contrib import admin

from facets.models import (
    District,
    RegisteredCommunityOrganization,
    StateHouseDistrict,
    StateSenateDistrict,
    ZipCode,
)
from pbaabp.admin import ReadOnlyLeafletGeoAdminMixin


class FacetAdmin(ReadOnlyLeafletGeoAdminMixin, admin.ModelAdmin):
    ordering = ("name",)

    def save_model(self, request, obj, form, change):
        if change:
            original_obj = type(obj).objects.get(pk=obj.pk)
            original_value = getattr(original_obj, "mpoly")
            obj.mpoly = original_value
            form.cleaned_data["mpoly"] = original_value

        super().save_model(request, obj, form, change)


class DistrictAdmin(FacetAdmin):
    list_display = ["name"]
    autocomplete_fields = ["organizers"]


class RegisteredCommunityOrganizationAdmin(FacetAdmin):
    list_display = ["name", "targetable"]
    list_filter = ["targetable"]
    search_fields = ["name"]
    readonly_fields = ("zip_code_names", "zip_codes")

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


class ZipCodeAdmin(FacetAdmin):
    list_display = ["name"]
    search_fields = ["name"]


class StateHouseDistrictAdmin(FacetAdmin):
    list_display = ["name"]
    search_fields = ["name"]


class StateSenateDistrictAdmin(FacetAdmin):
    list_display = ["name"]
    search_fields = ["name"]


admin.site.register(District, DistrictAdmin)
admin.site.register(RegisteredCommunityOrganization, RegisteredCommunityOrganizationAdmin)
admin.site.register(ZipCode, ZipCodeAdmin)
admin.site.register(StateHouseDistrict, StateHouseDistrictAdmin)
admin.site.register(StateSenateDistrict, StateSenateDistrictAdmin)
