from django.conf import settings
from django.core.management.base import BaseCommand

from facets.models import District
from pbaabp.email import send_email_message

district5 = District.objects.get(name="District 5")
district8 = District.objects.get(name="District 8")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        SENT = []
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in district5.contained_profiles.all():
            if profile.user.email not in SENT:
                send_email_message(
                    "speed_zone_cameras_2025_03_12/d5",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["district5@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
        SENT = []
        for profile in district8.contained_profiles.all():
            if profile.user.email not in SENT:
                send_email_message(
                    "speed_zone_cameras_2025_03_12/d8",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
