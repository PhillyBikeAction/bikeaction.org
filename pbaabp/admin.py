from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
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


class OrganizerAccess:
    def has_module_permission(self, request):
        if request.user.is_authenticated and request.user.profile.is_organizer:
            return True
        return super().has_module_permission(request)


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
