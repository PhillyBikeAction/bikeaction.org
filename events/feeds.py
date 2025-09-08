import datetime

from django.urls import reverse
from django_ical.views import ICalFeed

from events.models import ScheduledEvent


class AllEventsFeed(ICalFeed):
    product_id = "-//Philly Bike Action//PBA Events//EN"
    timezone = "UTC"
    file_name = "philly-bike-action-events.ics"
    title = "Philly Bike Action"
    description = "Events published by Philly Bike Action"
    ttl = "1H"

    def items(self):
        return (
            ScheduledEvent.objects.all()
            .exclude(status=ScheduledEvent.Status.DELETED)
            .exclude(hidden=True)
            .order_by("-start_datetime")
        )

    def item_guid(self, item):
        return item.id

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.description

    def item_location(self, item):
        return item.location

    def item_start_datetime(self, item):
        return item.start_datetime

    def item_end_datetime(self, item):
        if item.end_datetime is not None:
            return item.end_datetime
        return item.start_datetime + datetime.timedelta(hours=1)

    def item_link(self, item):
        return reverse("event_detail", args=[item.slug])
