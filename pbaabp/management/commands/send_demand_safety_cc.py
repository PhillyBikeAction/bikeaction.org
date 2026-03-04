from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand

from campaigns.models import PetitionSignature
from facets.models import District
from pbaabp.email import send_email_message

GEOJSON = """
{
        "coordinates": [
          [
            [
              -75.18832093534614,
              39.97531566575478
            ],
            [
              -75.17851387444026,
              39.95696726117416
            ],
            [
              -75.18062625534547,
              39.95002260438926
            ],
            [
              -75.16797284487963,
              39.94859690278406
            ],
            [
              -75.16722842771365,
              39.95154542935282
            ],
            [
              -75.15990796716083,
              39.95059426789729
            ],
            [
              -75.15842291250513,
              39.96191108007753
            ],
            [
              -75.16662751294899,
              39.97235780788685
            ],
            [
              -75.18832093534614,
              39.97531566575478
            ]
          ]
        ],
        "type": "Polygon"
}
"""

geom = GEOSGeometry(GEOJSON)

signatures = PetitionSignature.objects.filter(
    petition__title="Build the City Hall Bike Lane", location__within=geom
)
profiles = District.objects.get(name="District 5").contained_profiles.filter(location__within=geom)

SENT = []


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        print("Petitions!")
        for signature in signatures:
            if signature.email not in SENT:
                send_email_message(
                    "demand-safety-cc",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [signature.email],
                    {"first_name": signature.first_name, "petition": True},
                    reply_to=["district5@bikeaction.org"],
                )
                SENT.append(signature.email)
            else:
                print(f"skipping {signature}")
        print(len(SENT))
        print("Profiles!")
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "demand-safety-cc",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name},
                    reply_to=["district5@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
