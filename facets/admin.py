import csv

from django.contrib import admin
from django.db.models import Q
from django.db.models.functions import Length
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse

from facets.forms import COLUMN_CHOICES, CSVColumnSelectForm
from facets.models import (
    CongressionalDistrict,
    District,
    Division,
    RegisteredCommunityOrganization,
    StateHouseDistrict,
    StateSenateDistrict,
    Ward,
    ZipCode,
)
from pbaabp.admin import ReadOnlyLeafletGeoAdminMixin, organizer_admin
from profiles.models import Profile

COLUMN_ACCESSORS = {
    "first_name": lambda p: p.user.first_name,
    "last_name": lambda p: p.user.last_name,
    "email": lambda p: p.user.email,
    "pronouns": lambda p: p.pronouns or "",
    "street_address": lambda p: p.street_address or "",
    "zip_code": lambda p: p.zip_code or "",
    "newsletter_opt_in": lambda p: p.newsletter_opt_in,
    "created_at": lambda p: p.created_at.strftime("%Y-%m-%d %H:%M"),
    "district": lambda p: str(p.district) if p.district else "",
    "membership": lambda p: p.membership(),
    "donor": lambda p: p.donor(),
    "discord_active": lambda p: p.discord_active(),
    "discord_messages_last_30": lambda p: p.discord_messages_last_30(),
    "is_organizer": lambda p: p.is_organizer,
}


def _build_profiles_queryset(facets):
    q = Q()
    for facet in facets:
        q |= Q(location__within=facet.mpoly)
    return Profile.objects.filter(q).distinct().select_related("user")


def _build_facet_mapping(profiles, facets):
    mapping = {profile.pk: [] for profile in profiles}
    for facet in facets:
        for profile in profiles:
            if profile.location and facet.mpoly.contains(profile.location):
                mapping[profile.pk].append(facet.name)
    return mapping


def _build_csv_response(profiles, selected_columns, facets=None, facet_label="Facet"):
    column_labels = dict(COLUMN_CHOICES)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="profiles_export.csv"'
    writer = csv.writer(response)
    headers = [column_labels[col] for col in selected_columns]
    if facets is not None:
        headers.append(facet_label)
        facet_mapping = _build_facet_mapping(profiles, facets)
    writer.writerow(headers)
    for profile in profiles:
        row = [COLUMN_ACCESSORS[col](profile) for col in selected_columns]
        if facets is not None:
            row.append(", ".join(facet_mapping.get(profile.pk, [])))
        writer.writerow(row)
    return response


class FacetAdmin(ReadOnlyLeafletGeoAdminMixin, admin.ModelAdmin):
    ordering = ("name",)
    actions = ["export_profiles_csv"]
    change_form_template = "admin/facets/change_form.html"

    def save_model(self, request, obj, form, change):
        if change:
            original_obj = type(obj).objects.get(pk=obj.pk)
            original_value = getattr(original_obj, "mpoly")
            obj.mpoly = original_value
            form.cleaned_data["mpoly"] = original_value

        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        opts = self.model._meta
        custom_urls = [
            path(
                "<path:object_id>/export-csv/",
                self.admin_site.admin_view(self.export_single_csv_view),
                name=f"{opts.app_label}_{opts.model_name}_export_csv",
            ),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        opts = self.model._meta
        extra_context["export_csv_url_name"] = (
            f"admin:{opts.app_label}_{opts.model_name}_export_csv"
        )
        return super().change_view(request, object_id, form_url, extra_context)

    def export_single_csv_view(self, request, object_id):
        facet = self.model.objects.get(pk=object_id)
        opts = self.model._meta

        if request.method == "POST" and "confirm" in request.POST:
            form = CSVColumnSelectForm(request.POST)
            if form.is_valid():
                profiles = _build_profiles_queryset([facet])
                return _build_csv_response(
                    profiles,
                    form.cleaned_data["columns"],
                    facets=[facet],
                    facet_label=opts.verbose_name.title(),
                )

        profile_count = _build_profiles_queryset([facet]).count()
        changelist_url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
        export_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_export_csv", args=[object_id]
        )

        context = {
            **self.admin_site.each_context(request),
            "title": "Export Profiles as CSV",
            "app_label": opts.app_label,
            "model_name": opts.verbose_name_plural.title(),
            "changelist_url": changelist_url,
            "form_action_url": export_url,
            "cancel_url": reverse(
                f"admin:{opts.app_label}_{opts.model_name}_change", args=[object_id]
            ),
            "profile_count": profile_count,
            "facet_count": 1,
            "facet_names": str(facet),
            "selected_pks": [],
            "from_action": False,
            "form": CSVColumnSelectForm(),
        }
        return TemplateResponse(request, "admin/facets/csv_export_columns.html", context)

    @admin.action(description="Export contained profiles as CSV")
    def export_profiles_csv(self, request, queryset):
        opts = self.model._meta
        if "confirm" in request.POST:
            form = CSVColumnSelectForm(request.POST)
            if form.is_valid():
                profiles = _build_profiles_queryset(queryset)
                return _build_csv_response(
                    profiles,
                    form.cleaned_data["columns"],
                    facets=list(queryset),
                    facet_label=opts.verbose_name.title(),
                )

        profile_count = _build_profiles_queryset(queryset).count()
        changelist_url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")

        context = {
            **self.admin_site.each_context(request),
            "title": "Export Profiles as CSV",
            "app_label": opts.app_label,
            "model_name": opts.verbose_name_plural.title(),
            "changelist_url": changelist_url,
            "form_action_url": changelist_url,
            "cancel_url": changelist_url,
            "profile_count": profile_count,
            "facet_count": queryset.count(),
            "facet_names": ", ".join(str(f) for f in queryset),
            "selected_pks": [str(pk) for pk in queryset.values_list("pk", flat=True)],
            "from_action": True,
            "form": CSVColumnSelectForm(),
        }
        return TemplateResponse(request, "admin/facets/csv_export_columns.html", context)


class DistrictAdmin(FacetAdmin):
    ordering = (Length("name"), "name")
    list_display = ["name"]
    autocomplete_fields = ["organizers"]
    search_fields = ["name"]


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


class CongressionalDistrictAdmin(FacetAdmin):
    list_display = ["name"]
    search_fields = ["name"]


class WardAdmin(FacetAdmin):
    ordering = (Length("name"), "name")
    list_display = ["name"]
    search_fields = ["name"]


class DivisionAdmin(FacetAdmin):
    ordering = (Length("ward__name"), "ward__name", Length("name"), "name")
    list_display = ["name", "ward"]
    list_filter = ["ward"]
    search_fields = ["name"]


admin.site.register(District, DistrictAdmin)
admin.site.register(RegisteredCommunityOrganization, RegisteredCommunityOrganizationAdmin)
admin.site.register(ZipCode, ZipCodeAdmin)
admin.site.register(StateHouseDistrict, StateHouseDistrictAdmin)
admin.site.register(StateSenateDistrict, StateSenateDistrictAdmin)
admin.site.register(CongressionalDistrict, CongressionalDistrictAdmin)
admin.site.register(Ward, WardAdmin)
admin.site.register(Division, DivisionAdmin)
organizer_admin.register(District, DistrictAdmin)
organizer_admin.register(RegisteredCommunityOrganization, RegisteredCommunityOrganizationAdmin)
