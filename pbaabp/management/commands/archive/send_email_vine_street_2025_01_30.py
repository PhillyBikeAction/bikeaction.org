from django.conf import settings
from django.core.management.base import BaseCommand

from pbaabp.email import send_email_message
from profiles.models import Profile

TO = ["bikes@durbin.ee"]

profiles = Profile.objects.all()

profiles = Profile.objects.filter(user__email__in=TO)

SENT = []


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "vine_street_2025_01_30",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
