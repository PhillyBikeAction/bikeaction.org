from django.contrib import admin

from .models import Item, ItemType, Loan


class ItemTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "created_at", "updated_at"]
    search_fields = ["name", "description"]
    list_filter = ["created_at"]


class ItemAdmin(admin.ModelAdmin):
    list_display = ["name", "type__name", "total_quantity", "available_quantity", "created_at"]
    list_filter = ["type", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]


class LoanAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "item",
        "quantity",
        "active",
        "expected_return",
        "borrowed_at",
        "returned_at",
        "return_note",
        "created_at",
        "updated_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["user__username", "item__name"]
    date_hierarchy = "borrowed_at"


admin.site.register(Loan, LoanAdmin)
admin.site.register(ItemType, ItemTypeAdmin)
admin.site.register(Item, ItemAdmin)
