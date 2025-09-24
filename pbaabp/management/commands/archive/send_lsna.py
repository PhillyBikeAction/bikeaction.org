from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand

from campaigns.models import Petition
from pbaabp.email import send_email_message

GEOJSON = """
{
  "coordinates": [
    [
      [
        -75.17969186787991,
        39.96756926947026
      ],
      [
        -75.18306687597206,
        39.96454483083781
      ],
      [
        -75.17865340385147,
        39.958097554555735
      ],
      [
        -75.1811976407208,
        39.951450651921476
      ],
      [
        -75.16421875385794,
        39.94926141084116
      ],
      [
        -75.16375144504548,
        39.95168947398179
      ],
      [
        -75.16266105781577,
        39.95149045565611
      ],
      [
        -75.16250528821145,
        39.953122388836476
      ],
      [
        -75.16349182903814,
        39.953361205060446
      ],
      [
        -75.16022066734902,
        39.96721111924819
      ],
      [
        -75.17969186787991,
        39.96756926947026
      ]
    ]
  ],
  "type": "Polygon"
}
"""

geom = GEOSGeometry(GEOJSON)

signatures = (
    Petition.objects.get(slug="build-the-city-hall-bike-lane")
    .signatures.filter(location__within=geom)
    .all()
)
SENT = []


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for signature in signatures:
            if signature.email not in SENT:
                send_email_message(
                    "LSNA",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [signature.email],
                    {"first_name": signature.first_name},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(signature.email)
            else:
                print(f"skipping {signature}")
        print(len(SENT))
