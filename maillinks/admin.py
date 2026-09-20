from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from maillinks.models import MailLink
from pbaabp.admin import OrganizerPerms, organizer_admin


class MailLinkAdmin(admin.ModelAdmin):
    list_display = ["title", "active", "flyer", "page"]
    list_editable = ["active"]
    list_filter = ["active"]

    @admin.display(description="Flyer")
    def flyer(self, obj):
        return format_html(
            "<a href={url}>Flyer</a>", url=reverse("maillink_flyer", kwargs={"slug": obj.slug})
        )

    @admin.display(description="Page")
    def page(self, obj):
        return format_html(
            "<a href={url}>Page</a>", url=reverse("maillink_view", kwargs={"slug": obj.slug})
        )


class OrganizerMailLinkAdmin(OrganizerPerms, MailLinkAdmin):
    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(MailLink, MailLinkAdmin)
organizer_admin.register(MailLink, OrganizerMailLinkAdmin)
