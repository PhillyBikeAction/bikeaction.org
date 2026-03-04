from django.conf import settings
from django.core.management.base import BaseCommand

from facets.models import District
from pbaabp.email import send_email_message
from profiles.models import Profile

district = District.objects.get(name="District 2")

profiles = Profile.objects.filter(location__within=district.mpoly)
SENT = []


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "d2_volunteer_request",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["district-2@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
