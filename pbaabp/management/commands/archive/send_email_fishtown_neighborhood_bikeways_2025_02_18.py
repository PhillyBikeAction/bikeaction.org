from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand

from pbaabp.email import send_email_message
from profiles.models import Profile

GEOJSON = """
      {
        "coordinates": [
          [
            [
              -75.14656247510031,
              39.96118312734234
            ],
            [
              -75.13131838045685,
              39.959542548192616
            ],
            [
              -75.10896971974383,
              39.97163271309114
            ],
            [
              -75.11302776459596,
              39.9765997879463
            ],
            [
              -75.12227109417988,
              39.987072656439636
            ],
            [
              -75.12577551195493,
              39.990217448926074
            ],
            [
              -75.14020391066093,
              39.99206395702606
            ],
            [
              -75.14670074722164,
              39.96307214835514
            ],
            [
              -75.14656247510031,
              39.96118312734234
            ]
          ]
        ],
        "type": "Polygon"
      }
"""

geom = GEOSGeometry(GEOJSON)

profiles = Profile.objects.filter(location__within=geom)
SENT = []


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "fishtown_neighborhood_bikeways_2025_02_18",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
