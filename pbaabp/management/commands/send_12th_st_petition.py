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
              -75.18031304196629,
              39.963733199143206
            ],
            [
              -75.15761943022797,
              39.94736439752805
            ],
            [
              -75.1369745473265,
              39.96013964662865
            ],
            [
              -75.14300258083527,
              39.97004410888201
            ],
            [
              -75.15257644828708,
              39.970587604827045
            ],
            [
              -75.15948719297285,
              39.97146978392925
            ],
            [
              -75.18031304196629,
              39.963733199143206
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
                    "12th-st-petition",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
