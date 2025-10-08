from django.contrib import admin
from ordered_model.admin import OrderedModelAdmin

from membership.models import Donation, DonationProduct, DonationTier, Membership


class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "start_date", "end_date", "created_at")
    list_filter = ("kind", "start_date", "end_date")
    search_fields = ("user__email", "user__first_name", "user__last_name", "reason")
    autocomplete_fields = ("user",)
    date_hierarchy = "start_date"
    fields = ("user", "kind", "start_date", "end_date", "reason", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


class DonationTierAdmin(OrderedModelAdmin):
    list_display = ("__str__", "active", "move_up_down_links")
    list_filter = ("active",)
    ordering = ("-active", "order")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        else:
            return (
                "stripe_price",
                "cost",
                "recurrence",
            )


class DonationProductAdmin(admin.ModelAdmin):
    pass


class DonationAdmin(admin.ModelAdmin):
    list_filter = ("donation_product",)
    search_fields = ("comment",)


admin.site.register(Membership, MembershipAdmin)
admin.site.register(Donation, DonationAdmin)
admin.site.register(DonationTier, DonationTierAdmin)
admin.site.register(DonationProduct, DonationProductAdmin)
