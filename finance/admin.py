from csvexport.actions import csvexport
from django.contrib import admin

from finance.models import Reimbursement


class ReimbursementAdmin(admin.ModelAdmin):
    actions = [csvexport]
    list_display = ["get_name", "vendor_name", "amount", "expense_date", "reimbursement_method"]
    list_filter = ["reimbursement_method", "expense_date"]
    search_fields = ["first_name", "last_name", "email", "discord_handle", "vendor_name"]
    ordering = ["-created_at"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "first_name",
        "last_name",
        "email",
        "discord_handle",
        "vendor_name",
        "amount",
        "expense_date",
        "explanation",
        "expense_support",
        "reimbursement_method",
        "payment_contact",
    ]

    csvexport_selected_fields = [
        "created_at",
        "first_name",
        "last_name",
        "email",
        "discord_handle",
        "vendor_name",
        "amount",
        "expense_date",
        "explanation",
        "get_reimbursement_method_display",
        "payment_contact",
    ]

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


admin.site.register(Reimbursement, ReimbursementAdmin)
