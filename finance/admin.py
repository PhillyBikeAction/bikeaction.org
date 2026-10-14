from csvexport.actions import csvexport
from django.contrib import admin
from django.utils import timezone

from finance.models import Reimbursement, ReimbursementSupportingMaterial


@admin.action(description="Mark selected reimbursements as completed")
def mark_completed(modeladmin, request, queryset):
    queryset.update(completed=True)


class ReimbursementSupportingMaterialInline(admin.TabularInline):
    model = ReimbursementSupportingMaterial
    extra = 0


class ReimbursementAdmin(admin.ModelAdmin):
    inlines = (ReimbursementSupportingMaterialInline,)
    actions = [csvexport, mark_completed]
    list_display = [
        "get_name",
        "vendor_name",
        "amount",
        "expense_date",
        "reimbursement_method",
        "decision",
        "completed",
    ]
    list_filter = ["decision", "completed", "reimbursement_method", "expense_date"]
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
        "reimbursement_method",
        "payment_contact",
        "decided_at",
        "decided_by",
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
        "get_decision_display",
        "decided_at",
        "decided_by",
        "completed",
    ]

    def save_model(self, request, obj, form, change):
        if "decision" in form.changed_data:
            if obj.decision == Reimbursement.Decision.PENDING:
                obj.decided_at = None
                obj.decided_by = None
            else:
                obj.decided_at = timezone.now()
                obj.decided_by = str(request.user)
        super().save_model(request, obj, form, change)

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


admin.site.register(Reimbursement, ReimbursementAdmin)
