from csvexport.actions import csvexport
from django.contrib import admin

from events.models import EventRSVP, EventSignIn, ScheduledEvent
from pbaabp.admin import OrganizerPerms, organizer_admin


class ScheduledEventAdmin(admin.ModelAdmin):
    list_display = ["title", "start_datetime", "status"]
    list_filter = ["status"]
    ordering = ["-status", "start_datetime"]
    search_fields = ["title", "districts", "registered_community_organizations"]


class OrganizerScheduledEventAdmin(OrganizerPerms, ScheduledEventAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if obj:
            return set(request.user.profile.organized_districts.all()).intersection(
                set(obj.districts.all())
            )
        return False

    def has_delete_permission(self, request, obj=None):
        if obj:
            return set(request.user.profile.organized_districts.all()).intersection(
                set(obj.districts.all())
            )
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(districts__in=request.user.profile.organized_districts.all())
            .distinct()
        )


class EventSignInAdmin(admin.ModelAdmin):
    actions = [csvexport]
    list_display = ["get_name", "get_event", "newsletter_opt_in"]
    list_filter = ["event__title"]
    search_fields = ["first_name", "last_name", "email"]
    ordering = ["-updated_at"]
    readonly_fields = [
        "event",
        "mailjet_contact_id",
        "first_name",
        "last_name",
        "email",
        "newsletter_opt_in",
    ]

    csvexport_selected_fields = [
        "first_name",
        "last_name",
        "email",
        "event.title",
    ]

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_event(self, obj):
        return obj.event.title


class OrganizerEventSignInAdmin(OrganizerPerms, EventSignInAdmin):
    actions = []
    list_display = ["get_name", "get_event", "newsletter_opt_in"]
    list_filter = ["event__title"]
    search_fields = ["first_name", "last_name"]
    fields = [
        "event",
        "first_name",
        "last_name",
        "newsletter_opt_in",
    ]
    readonly_fields = [
        "event",
        "first_name",
        "last_name",
        "newsletter_opt_in",
    ]

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(event__districts__in=request.user.profile.organized_districts.all())
            .distinct()
        )


class EventRSVPAdmin(admin.ModelAdmin):
    actions = [csvexport]
    list_display = ["get_name", "get_event"]
    list_filter = ["event__title"]
    search_fields = ["first_name", "last_name", "email"]
    readonly_fields = ["event", "user", "first_name", "last_name", "email"]

    def get_name(self, obj):
        if obj.user is None:
            return f"{obj.first_name} {obj.last_name}"
        return f"{obj.user.first_name} {obj.user.last_name}"

    def get_event(self, obj):
        return obj.event.title


class OrganizerEventRSVPAdmin(OrganizerPerms, EventRSVPAdmin):
    actions = []
    list_display = ["get_name", "get_event"]
    list_filter = ["event__title"]
    search_fields = ["first_name", "last_name"]
    fields = ["event", "first_name", "last_name"]
    readonly_fields = ["event", "first_name", "last_name"]

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(event__districts__in=request.user.profile.organized_districts.all())
            .distinct()
        )


admin.site.register(ScheduledEvent, ScheduledEventAdmin)
admin.site.register(EventSignIn, EventSignInAdmin)
admin.site.register(EventRSVP, EventRSVPAdmin)
organizer_admin.register(ScheduledEvent, OrganizerScheduledEventAdmin)
organizer_admin.register(EventSignIn, OrganizerEventSignInAdmin)
organizer_admin.register(EventRSVP, OrganizerEventRSVPAdmin)
