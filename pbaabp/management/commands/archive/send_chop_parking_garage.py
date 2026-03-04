from django.conf import settings
from django.core.management.base import BaseCommand

from facets.models import District
from pbaabp.email import send_email_message
from profiles.models import Profile

district = District.objects.get(name="District 2")
profiles = Profile.objects.filter(location__within=district.mpoly)

SENT = []


class Command(BaseCommand):
    def handle(*args, **kwargs):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "chop_parking_garage",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name},
                    reply_to=["district2@bikeaction.org"],
                )
                SENT.append(profile.user.email.lower())
            else:
                print(f"skipping {profile}")

        print(len(SENT))
