from django.conf import settings
from django.core.management.base import BaseCommand

from pbaabp.email import send_email_message
from profiles.models import Profile

profiles = Profile.objects.all()

SENT = []


class Command(BaseCommand):

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "demand-a-safer-fairmount-park",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
