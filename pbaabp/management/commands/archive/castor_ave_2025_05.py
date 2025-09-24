from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from facets.models import District
from pbaabp.email import send_email_message
from profiles.models import Profile

district6 = District.objects.get(name="District 6")
district7 = District.objects.get(name="District 7")
district8 = District.objects.get(name="District 8")
district9 = District.objects.get(name="District 9")
profiles = Profile.objects.filter(
    Q(location__within=district6.mpoly)
    | Q(location__within=district7.mpoly)
    | Q(location__within=district8.mpoly)
    | Q(location__within=district9.mpoly)
)

SENT = []


class Command(BaseCommand):

    def handle(*args, **kwargs):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "castor_ave_2025_05",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name, "district": profile.district},
                    reply_to=["district3@bikeaction.org"],
                )
                SENT.append(profile.user.email.lower())
            else:
                print(f"skipping {profile}")

        print(len(SENT))
