from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from campaigns.models import Campaign


class CampaignSitemap(Sitemap):
    def items(self):
        return Campaign.objects.filter(
            visible=True, status__in=[Campaign.Status.ACTIVE, Campaign.Status.COMPLETED]
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse("campaign", kwargs={"slug": obj.slug})
