from django.urls import path

from events import feeds, views

urlpatterns = [
    path("", views.EventsListView.as_view(), name="events_list"),
    path("past/", views.PastEventsListView.as_view(), name="events_past_list"),
    path("<slug:slug>/", views.EventDetailView.as_view(), name="event_detail"),
    path("<slug:event_slug_or_id>/rsvp/", views.event_rsvp, name="event_rsvp"),
    path("<slug:event_slug_or_id>/rsvp/cancel/", views.event_rsvp_cancel, name="event_rsvp_cancel"),
    path("<slug:event_slug_or_id>/signin/", views.event_signin, name="event_signin"),
    path(
        "<slug:event_slug_or_id>/kiosk-postroll/",
        views.event_signin_kiosk_postroll,
        name="event_signin_kiosk_postroll",
    ),
    path("calendar/all/", feeds.AllEventsFeed(), name="events_feed_all"),
]
