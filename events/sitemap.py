from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from events.models import ScheduledEvent


class ScheduledEventSitemap(Sitemap):
    def items(self):
        return ScheduledEvent.objects.filter(
            status__in=[
                ScheduledEvent.Status.SCHEDULED,
                ScheduledEvent.Status.ACTIVE,
                ScheduledEvent.Status.COMPLETED,
            ]
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse("event_detail", kwargs={"slug": obj.slug})
