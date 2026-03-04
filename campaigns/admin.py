import hashlib
import json

from csvexport.actions import csvexport
from django.contrib import admin
from django.db.models import Q
from django.shortcuts import render
from ordered_model.admin import OrderedModelAdmin

from campaigns.models import Campaign, Petition, PetitionCheckbox, PetitionSignature
from campaigns.tasks import geocode_signature
from facets.models import District, RegisteredCommunityOrganization
from pbaabp.admin import ReadOnlyLeafletGeoAdminMixin, organizer_admin


class CampaignAdmin(OrderedModelAdmin):
    readonly_fields = ["wordpress_id", "donation_total"]
    autocomplete_fields = ["events", "districts", "registered_community_organizations"]
    list_display = ("__str__", "status", "visible", "get_districts", "move_up_down_links")
    list_filter = ["status", "visible"]
    ordering = ("status", "order")

    def get_districts(self, obj):
        return ", ".join(d.name.lstrip("District ") for d in obj.districts.all())

    def get_form(self, *args, **kwargs):
        help_texts = {
            "donation_action": "Encourage one-time donation",
            "subscription_action": "Encourage recurring donation",
        }
        kwargs.update({"help_texts": help_texts})
        return super().get_form(*args, **kwargs)


def pretty_report(modeladmin, request, queryset):
    _petitions = {}
    for petition in queryset:
        signatures = sorted(
            list(petition.signatures.order_by("email").distinct("email").all()),
            key=lambda x: x.created_at,
        )
        district_counts = {}
        for district in District.objects.all():
            cnt = (
                petition.signatures.filter(location__within=district.mpoly)
                .distinct("email")
                .count()
            )
            if cnt > 0:
                district_counts[district.name] = cnt
        _petitions[petition] = {
            "signatures": signatures,
            "total_count": len(signatures),
            "district_counts": district_counts,
        }
    return render(request, "petition_signatures_pretty_report.html", {"petitions": _petitions})


class OrganizerCampaignAdmin(CampaignAdmin):
    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        if obj:
            return set(request.user.profile.organized_districts.all()).intersection(
                set(obj.districts.all())
            )
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PetitionCheckboxInline(admin.TabularInline):
    model = PetitionCheckbox
    fields = ["label", "help_text", "required"]
    ordering = ["order"]
    extra = 0

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "label":
            field.help_text = "Cannot be changed after creation"
        return field

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        original_init = formset.form.__init__

        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            if self.instance and self.instance.pk:
                self.fields["label"].disabled = True

        formset.form.__init__ = new_init
        return formset


class PetitionAdmin(admin.ModelAdmin):
    actions = [pretty_report]
    readonly_fields = ["petition_report"]
    inlines = [PetitionCheckboxInline]

    def petition_report(self, obj):
        report = ""
        totalsigs = obj.signatures.count()
        report += f"Total signatures: {totalsigs}\n"
        totaldistinctsigs = obj.signatures.distinct("email").count()
        report += f"Total signatures (distinct by email): {totaldistinctsigs}\n\n"
        nongeocoded = obj.signatures.distinct("email").filter(location=None).count()
        report += f"Non-geocoded signatures: {nongeocoded}\n\n"
        report += "Districts:\n"
        philly = 0
        for district in District.objects.all():
            cnt = obj.signatures.filter(location__within=district.mpoly).distinct("email").count()
            philly += cnt
            report += f"{district.name}: {cnt}\n"
        report += f"\nAll of Philadelphia: {philly}\n"
        report += "\nRCOs:\n"
        for rco in RegisteredCommunityOrganization.objects.all():
            cnt = obj.signatures.filter(location__within=rco.mpoly).distinct("email").count()
            report += f"{rco.name}: {cnt}\n"
        return report

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        q_objects = Q()
        for district in request.user.profile.organized_districts.all():
            q_objects |= Q(campaign__districts__in=[district])
        qs = qs.filter(q_objects)
        return qs


class OrganizerPetitionAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        if obj:
            return set(request.user.profile.organized_districts.all()).intersection(
                set(obj.campaign.districts.all())
            )
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def geocode(modeladmin, request, queryset):
    for obj in queryset:
        if obj.location is None:
            geocode_signature.delay(obj.id)


def randomize_lat_long(salt, lat, long):
    hash = hashlib.sha256(f"{salt}-{lat}-{long}".encode())
    smear_int = int.from_bytes(hash.digest(), "big")
    x_smear = (((smear_int % 2179) / 2179) - 0.5) * 0.000287
    y_smear = (((smear_int % 2803) / 2803) - 0.5) * 0.000358
    return (lat + x_smear, long + y_smear)


def heatmap(modeladmin, request, queryset):
    pins = []
    for signature in queryset:
        if signature.location:
            lat, lng = randomize_lat_long(
                signature.petition.id, signature.location.y, signature.location.x
            )
            pins.append([lat, lng, 1])
    return render(request, "petition/heatmap.html", {"pins_json": json.dumps(pins)})


class DistrictFilter(admin.SimpleListFilter):
    title = "District"
    parameter_name = "district"

    def lookups(self, request, model_amin):
        return [(f.id, f.name) for f in District.objects.all() if f.targetable]

    def queryset(self, request, queryset):
        if self.value():
            d = District.objects.get(id=self.value())
            return queryset.filter(location__within=d.mpoly)
        return queryset


class CheckboxResponseFilter(admin.SimpleListFilter):
    title = "Checkbox Response"
    parameter_name = "checkbox_response"

    def lookups(self, request, model_admin):
        petition_id = request.GET.get("petition__id__exact") or request.GET.get("petition")

        if petition_id:
            checkboxes = PetitionCheckbox.objects.filter(petition_id=petition_id)
            lookups = []
            for checkbox in checkboxes:
                lookups.append((f"{checkbox.label}:true", f"{checkbox.label}: Yes"))
                lookups.append((f"{checkbox.label}:false", f"{checkbox.label}: No"))
        else:
            checkboxes = PetitionCheckbox.objects.select_related("petition").all()
            lookups = []
            for checkbox in checkboxes:
                petition_title = str(checkbox.petition)[:20]
                lookups.append(
                    (f"{checkbox.label}:true", f"{petition_title}... - {checkbox.label}: Yes")
                )
                lookups.append(
                    (f"{checkbox.label}:false", f"{petition_title}... - {checkbox.label}: No")
                )
        return lookups

    def queryset(self, request, queryset):
        if self.value():
            label, value = self.value().rsplit(":", 1)
            checked = value == "true"
            return queryset.filter(checkbox_responses__contains={label: checked})
        return queryset


class PetitionSignatureAdmin(admin.ModelAdmin, ReadOnlyLeafletGeoAdminMixin):
    actions = [csvexport, geocode, heatmap]
    list_display = [
        "get_name",
        "email",
        "zip_code",
        "created_at",
        "has_comment",
        "visible",
        "get_petition",
    ]
    list_filter = ["petition", "visible", DistrictFilter, CheckboxResponseFilter]
    ordering = ["-created_at"]
    search_fields = ["first_name", "last_name", "comment", "email", "zip_code"]
    readonly_fields = [
        "first_name",
        "last_name",
        "email",
        "postal_address_line_1",
        "postal_address_line_2",
        "city",
        "state",
        "zip_code",
        "comment",
        "petition",
        "created_at",
        "checkbox_responses_display",
    ]

    def checkbox_responses_display(self, obj):
        if not obj.checkbox_responses:
            return "-"
        lines = []
        for label, checked in obj.checkbox_responses.items():
            status = "Yes" if checked else "No"
            lines.append(f"{label}: {status}")
        return "\n".join(lines) if lines else "-"

    checkbox_responses_display.short_description = "Checkbox Responses"

    csvexport_selected_fields = [
        "first_name",
        "last_name",
        "email",
        "postal_address_line_1",
        "postal_address_line_2",
        "city",
        "state",
        "zip_code",
        "comment",
        "petition.title",
        "checkbox_responses",
    ]

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    get_name.short_description = "Name"

    def get_petition(self, obj):
        return str(obj.petition)[:37] + "..." if len(str(obj.petition)) > 37 else ""

    get_petition.short_description = "Petition"

    def has_comment(self, obj):
        return bool(obj.comment)

    has_comment.boolean = True


class OrganizerPetitionSignatureAdmin(PetitionSignatureAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        q_objects = Q()
        for district in request.user.profile.organized_districts.all():
            q_objects |= Q(petition__campaign__districts__in=[district])
        qs = qs.filter(q_objects)
        return qs


admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Petition, PetitionAdmin)
admin.site.register(PetitionSignature, PetitionSignatureAdmin)
organizer_admin.register(Campaign, OrganizerCampaignAdmin)
organizer_admin.register(Petition, OrganizerPetitionAdmin)
organizer_admin.register(PetitionSignature, OrganizerPetitionSignatureAdmin)
