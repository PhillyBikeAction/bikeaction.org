from admin_extra_buttons.api import ExtraButtonsMixin, button
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone

from pbaabp.admin import OrganizerAccess, organizer_admin

from .models import Item, ItemType, Loan
from .admin_views import checkout_items, return_items


class ItemTypeOrganizerAdmin(OrganizerAccess, admin.ModelAdmin):
    list_display = ["name", "description"]
    search_fields = ["name", "description"]


class ItemOrganizerAdmin(OrganizerAccess, admin.ModelAdmin):
    list_display = ["name", "type__name", "total_quantity", "available_quantity"]
    search_fields = ["name"]


class LoanOrganizerAdmin(ExtraButtonsMixin, OrganizerAccess, admin.ModelAdmin):
    list_display = ["user", "item", "quantity", "expected_return", "checkout_note", "borrowed_at"]
    search_fields = ["user__username", "item__name"]
    date_hierarchy = "borrowed_at"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(active=True)

    @button(
        label="Checkout Items",
        change_list=True,
        html_attrs={"style": "background-color: green; color: white;"},
    )
    def checkout_button(self, request):
        return redirect("organizer_admin:locker_loan_checkout")

    @button(
        label="Return Items",
        change_list=True,
        html_attrs={"style": "background-color: orange; color: white;"},
    )
    def return_button(self, request):
        return redirect("organizer_admin:locker_loan_return")

    @button(
        label="Return All Items",
        html_attrs={
            "onclick": 'return confirm("Are you sure you want to return all active items?");',
            "style": "background-color: red; color: white;",
        },
    )
    def return_all(self, request):
        user = request.user

        queryset = Loan.objects.filter(user=user, active=True)

        if not queryset.exists():
            messages.warning(request, "You have no active loans to return.")
            return
        c = queryset.count()
        # Update inventory
        for obj in queryset:
            item = obj.item
            item.available_quantity += obj.quantity
            item.save()

        # Update the loans
        queryset.update(active=False, returned_at=timezone.now())

        self.message_user(
            request,
            f"{c} loans marked as returned.",
            messages.SUCCESS,
        )

    @button(label="Return Item", change_form=True, change_list=True, css_class="deletelink")
    def return_item(self, request, pk):
        obj = self.get_object(request, pk)
        if obj.user != request.user:
            messages.error(request, "You can only edit your own loans.")
            return
        item = obj.item
        item.available_quantity += obj.quantity
        item.save()

        obj.active = False
        obj.returned_at = timezone.now()
        obj.save()

        self.message_user(request, f"Loan {obj} returned.")
        return redirect("organizer_admin:locker_loan_changelist")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "checkout/",
                self.admin_site.admin_view(checkout_items),
                name="locker_loan_checkout",
            ),
            path(
                "return/",
                self.admin_site.admin_view(return_items),
                name="locker_loan_return",
            ),
        ]
        return custom_urls + urls
    # hide default add
    def has_add_permission(self, request):
        return False


organizer_admin.register(Loan, LoanOrganizerAdmin)
organizer_admin.register(ItemType, ItemTypeOrganizerAdmin)
organizer_admin.register(Item, ItemOrganizerAdmin)
