from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from maillinks.models import MailLink


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


admin.site.register(MailLink, MailLinkAdmin)
