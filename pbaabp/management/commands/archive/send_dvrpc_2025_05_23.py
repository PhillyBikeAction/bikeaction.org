from django.conf import settings
from django.core.management.base import BaseCommand

from pbaabp.email import send_email_message
from profiles.models import Profile


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        SENT = []
        settings.EMAIL_SUBJECT_PREFIX = ""
        SENT = []
        for profile in Profile.objects.all():
            if profile.user.email not in SENT:
                send_email_message(
                    "dvrpc_2025_05_23",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
