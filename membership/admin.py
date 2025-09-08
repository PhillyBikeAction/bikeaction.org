from django.contrib import admin
from ordered_model.admin import OrderedModelAdmin

from membership.models import Donation, DonationProduct, DonationTier, Membership


class MembershipAdmin(admin.ModelAdmin):
    pass


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
