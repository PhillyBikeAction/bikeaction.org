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
              -75.13491395041538,
              39.96513163565882
            ],
            [
              -75.16044171374598,
              39.961910063155045
            ],
            [
              -75.16390848636992,
              39.94392688479917
            ],
            [
              -75.13917986082144,
              39.93498161810891
            ],
            [
              -75.1374460156757,
              39.94939415098807
            ],
            [
              -75.13491395041538,
              39.96513163565882
            ]
          ]
  ],
  "type": "Polygon"
}
"""

geom = GEOSGeometry(GEOJSON)

profiles = Profile.objects.filter(location__within=geom).all()
SENT = []


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "mkt-st-ride",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
