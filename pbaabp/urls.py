import os
from pathlib import Path

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views import static as static_view
from django.views.generic.base import RedirectView
from sesame.views import LoginView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps.sitemap_generator import Sitemap as WagtailSitemap
from wagtail.contrib.sitemaps.views import sitemap as wagtail_sitemap
from wagtail.documents import urls as wagtaildocs_urls

from campaigns.sitemap import CampaignSitemap
from events.sitemap import ScheduledEventSitemap

# from lazer.views import list as laser_list
from lazer.views import map as laser_map
from lazer.views import map_data as laser_map_data
from lazer.views import my_wrapped as laser_my_wrapped
from lazer.views import wrapped as laser_wrapped
from pbaabp.admin import organizer_admin
from pbaabp.views import (
    EmailLoginView,
    _newsletter_signup_partial,
    email_draft,
    email_draft_image,
    email_draft_preview,
    mailjet_unsubscribe,
    newsletter_bridge,
    wagtail_pages,
)

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("accounts/profile/", include("profiles.urls")),
    path("events/", include("events.urls")),
    path("release/", include("release.urls")),
    path("donations/", include("membership.urls")),
    path("campaigns/", include("campaigns.urls")),
    path("elections/", include("elections.urls")),
    path("stripe/", include("djstripe.urls", namespace="djstripe")),
    path("sesame/login/", LoginView.as_view(), name="sesame_login"),
    path("email/login/", EmailLoginView.as_view(), name="email_login"),
    path("email-draft/", email_draft, name="email_draft"),
    path("email-draft/preview/", email_draft_preview, name="email_draft_preview"),
    path("email-draft/image/<str:filename>", email_draft_image, name="email_draft_image"),
    path("maillink/", include("maillinks.urls")),
    path("rcos/", include("facets.urls")),
    path("projects/", include("projects.urls")),
    path("organizers/", include("organizers.urls")),
    path(
        "_partials/_newsletter_signup_partial/",
        _newsletter_signup_partial,
        name="newsletter_signup_partial",
    ),
    path("lazer/", include("lazer.urls")),
    re_path(
        r"^laser/(?:index.html)?$",
        static_view.serve,
        {
            "document_root": os.path.join(settings.BASE_DIR, Path("static/lazer")),
            "path": "index.html",
        },
    ),
    re_path(r"laser/home/?$", RedirectView.as_view(url="/laser/")),
    re_path(r"laser/history/?$", RedirectView.as_view(url="/laser/")),
    re_path(
        r"^laser/(?P<path>.*)$",
        static_view.serve,
        {"document_root": os.path.join(settings.BASE_DIR, Path("static/lazer"))},
    ),
    path("tools/laser/map/", laser_map),
    path("tools/laser/map_data/", laser_map_data),
    # path("tools/laser/list/", laser_list),
    path("tools/laser/wrapped/", laser_my_wrapped, name="laser_my_wrapped"),
    path("tools/laser/wrapped/<str:share_token>/", laser_wrapped, name="laser_wrapped"),
    path("", include("pages.urls")),
    path("admin/", admin.site.urls),
    path("organizer/", organizer_admin.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path(f"mailjet/{settings.MAILJET_SECRET_SIGNUP_URL}/", newsletter_bridge),
    path("mailjet/unsubscribe/", mailjet_unsubscribe),
    path(
        "sitemap.xml",
        wagtail_sitemap,
        {
            "sitemaps": {
                "pages": WagtailSitemap,
                "campaigns": CampaignSitemap,
                "events": ScheduledEventSitemap,
            }
        },
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("qr_code/", include("qr_code.urls", namespace="qr_code")),
    path("cms_pages/", wagtail_pages),
    path("", include(wagtail_urls)),
]

if settings.DEBUG:
    urlpatterns.insert(0, path("__debug__/", include("debug_toolbar.urls")))
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
