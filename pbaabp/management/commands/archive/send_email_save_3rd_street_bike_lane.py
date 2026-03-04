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
        -75.1400548062263,
        39.944527730154704
      ],
      [
        -75.13324382088838,
        39.96039131395358
      ],
      [
        -75.13431267461449,
        39.9688012825701
      ],
      [
        -75.13801755516154,
        39.96945651002534
      ],
      [
        -75.15019866245962,
        39.9705482111645
      ],
      [
        -75.16480469701393,
        39.972348913735345
      ],
      [
        -75.1925877729296,
        39.97562589025023
      ],
      [
        -75.18625694464642,
        39.9670700750554
      ],
      [
        -75.17947111716111,
        39.959042393731636
      ],
      [
        -75.18149404725956,
        39.951554565405075
      ],
      [
        -75.18613914729148,
        39.9475399210192
      ],
      [
        -75.19375781386567,
        39.94224386254194
      ],
      [
        -75.19864210964984,
        39.9433404050794
      ],
      [
        -75.20363973164312,
        39.94324780881283
      ],
      [
        -75.20506880475773,
        39.93850093514919
      ],
      [
        -75.20352146663043,
        39.935123135344156
      ],
      [
        -75.2022144747498,
        39.920056479018
      ],
      [
        -75.19792681456966,
        39.89831870838836
      ],
      [
        -75.1664915935656,
        39.897223746033575
      ],
      [
        -75.1362479094133,
        39.90462250995739
      ],
      [
        -75.13910531978753,
        39.92480558250608
      ],
      [
        -75.1401742707819,
        39.93384523743646
      ],
      [
        -75.1400548062263,
        39.944527730154704
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
                    "save_3rd_street_bike_lane",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
