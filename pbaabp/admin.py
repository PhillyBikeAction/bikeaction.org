from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from djstripe.models import WebhookEndpoint
from leaflet.admin import LeafletGeoAdminMixin


class ReadOnlyLeafletGeoAdminMixin(LeafletGeoAdminMixin):
    modifiable = False


app_models = apps.get_app_config("djstripe").get_models()
for model in app_models:
    if model != WebhookEndpoint:
        try:
            admin.site.unregister(model)
        except NotRegistered:
            pass

app_models = apps.get_app_config("wagtaildocs").get_models()
for model in app_models:
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass

app_models = apps.get_app_config("wagtailimages").get_models()
for model in app_models:
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass


class OrganizerPerms:
    """Mixin for ModelAdmins registered on `organizer_admin`. Grants module/view
    access to organizers without going through Django's global perm system, so
    these grants don't bleed into the default `admin.site`.
    """

    def has_module_permission(self, request):
        return bool(request.user.is_authenticated and request.user.profile.is_organizer)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def lookup_allowed(self, lookup, value, request=None):
        # The hidden reverse relations on the join tables can also identify affiliated people.
        private_lookups = {
            "affiliation",
            "affiliations",
            "Profile_affiliations+",
            "PetitionSignature_affiliations+",
        }
        if private_lookups.intersection(lookup.split("__")):
            return False
        return super().lookup_allowed(lookup, value, request)


class OrganizerAuthenticationForm(AuthenticationForm):
    """
    A custom authentication form used in the organizer admin app.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": _(
            "Please enter the correct %(username)s and password for a organizer"
            "account. Note that both fields may be case-sensitive."
        ),
    }
    required_css_class = "required"

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.profile.is_organizer or user.is_staff:
            raise ValidationError(
                self.error_messages["invalid_login"],
                code="invalid_login",
                params={"username": self.username_field.verbose_name},
            )


class OrganizerAdminSite(admin.AdminSite):
    site_header = "PBA Organizer Admin"
    site_title = "PBA Organzier Admin"
    index_title = "Welcome to the PBA Organizer Admin"
    login_form = OrganizerAuthenticationForm

    def has_permission(self, request):
        if request.user.is_authenticated:
            return request.user.profile.is_organizer
        return False

    def has_module_permission(self, request):
        if request.user.is_authenticated:
            return request.user.profile.is_organizer
        return False


organizer_admin = OrganizerAdminSite(name="organizer_admin")
organizer_admin.disable_action("delete_selected")


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin):
    list_display = ("name", "member_count")
    readonly_fields = ("members_list",)
    fieldsets = ((None, {"fields": ("name", "permissions", "members_list")}),)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("user_set")

    @admin.display(description="Members", ordering="user_set__count")
    def member_count(self, obj):
        return obj.user_set.count()

    @admin.display(description="Members")
    def members_list(self, obj):
        users = obj.user_set.order_by("last_name", "first_name", "username")
        if not users:
            return "—"
        return format_html_join(
            format_html("<br>"),
            '<a href="{}">{}</a>',
            (
                (
                    reverse("admin:auth_user_change", args=[u.pk]),
                    u.get_full_name() or u.username,
                )
                for u in users
            ),
        )
