from django.contrib import admin

from community_fund.models import (
    CommunityActionFundApplication,
    CommunityActionFundApplicationPeriod,
    CommunityActionFundSupportingMaterial,
)


@admin.register(CommunityActionFundApplicationPeriod)
class CommunityActionFundApplicationPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "starts_at", "ends_at")
    ordering = ("-starts_at",)


class CommunityActionFundSupportingMaterialInline(admin.TabularInline):
    model = CommunityActionFundSupportingMaterial
    extra = 0


@admin.register(CommunityActionFundApplication)
class CommunityActionFundApplicationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "submitter", "draft", "decision", "created_at")
    list_filter = ("draft", "decision")
    readonly_fields = ("markdown", "created_at", "updated_at")
    inlines = (CommunityActionFundSupportingMaterialInline,)
