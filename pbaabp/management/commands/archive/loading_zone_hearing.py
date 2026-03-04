from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from facets.models import District
from pbaabp.email import send_email_message
from profiles.models import Profile

district1 = District.objects.get(name="District 1")
district2 = District.objects.get(name="District 2")
profiles = Profile.objects.filter(
    Q(location__within=district1.mpoly) | Q(location__within=district2.mpoly)
)

SENT = []


class Command(BaseCommand):
    def handle(*args, **kwargs):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "loading_zone_hearing",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name, "district": profile.district.name},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email.lower())
            else:
                print(f"skipping {profile}")

        print(len(SENT))
