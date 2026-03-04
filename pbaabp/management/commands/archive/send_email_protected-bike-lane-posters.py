from django.conf import settings
from django.core.management.base import BaseCommand

from pbaabp.email import send_email_message
from profiles.models import Profile

TO = ["bikes@durbin.ee", "jjamadio@gmail.com", "shawnbachman@gmail.com"]

profiles = Profile.objects.all()

profiles = Profile.objects.filter(user__email__in=TO)

SENT = []


class Command(BaseCommand):
    def handle(*args, **kwargs):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "protected-bike-lanes-posters",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["posters@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
