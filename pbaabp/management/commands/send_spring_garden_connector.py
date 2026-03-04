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
              -75.12223975016943,
              39.98707808432479
            ],
            [
              -75.13314314756038,
              39.98262173677662
            ],
            [
              -75.13473971410473,
              39.97527242895751
            ],
            [
              -75.18859833165139,
              39.982711996983795
            ],
            [
              -75.1896555615568,
              39.97794006698294
            ],
            [
              -75.17980798287408,
              39.95967334710289
            ],
            [
              -75.18038389753401,
              39.95154063274137
            ],
            [
              -75.13633185049808,
              39.94573843218612
            ],
            [
              -75.11191006955677,
              39.976053710549024
            ],
            [
              -75.12223975016943,
              39.98707808432479
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
    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "spring-garden-connector",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
