from csvexport.actions import csvexport
from django.contrib import admin
from django.db.models import Q
from ordered_model.admin import OrderedModelAdmin

from campaigns.models import Campaign, Petition, PetitionSignature
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


class PetitionAdmin(admin.ModelAdmin):
    readonly_fields = ["petition_report"]

    def petition_report(self, obj):
        report = ""
        totalsigs = obj.signatures.count()
        report += f"Total signatures: {totalsigs}\n"
        nongeocoded = obj.signatures.filter(location=None).count()
        report += f"Non-geocoded signatures: {nongeocoded}\n\n"
        report += "Districts:\n"
        philly = 0
        for district in District.objects.all():
            cnt = obj.signatures.filter(location__within=district.mpoly).count()
            philly += cnt
            report += f"{district.name}: {cnt}\n"
        report += f"\nAll of Philadelphia: {philly}\n"
        report += "\nRCOs:\n"
        for rco in RegisteredCommunityOrganization.objects.all():
            cnt = obj.signatures.filter(location__within=rco.mpoly).count()
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


class PetitionSignatureAdmin(admin.ModelAdmin, ReadOnlyLeafletGeoAdminMixin):
    actions = [csvexport, geocode]
    list_display = [
        "get_name",
        "email",
        "zip_code",
        "created_at",
        "has_comment",
        "visible",
        "get_petition",
    ]
    list_filter = ["petition", "visible"]
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
    ]

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
