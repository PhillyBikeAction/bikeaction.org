from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from leaflet.admin import LeafletGeoAdminMixin


class ReadOnlyLeafletGeoAdminMixin(LeafletGeoAdminMixin):
    modifiable = False


app_models = apps.get_app_config("djstripe").get_models()
for model in app_models:
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass


class OrganizerAdminSite(admin.AdminSite):
    site_header = "PBA Organizer Admin"
    site_title = "PBA Organzier Admin"
    index_title = "Welcome to the PBA Organizer Admin"

    def has_permission(self, request):
        return request.user.profile.is_organizer


organizer_admin = OrganizerAdminSite(name="organizer_admin")
organizer_admin.disable_action("delete_selected")
