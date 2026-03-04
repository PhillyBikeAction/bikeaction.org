from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from events.models import EventSignIn, ScheduledEvent
from facets.models import District
from pbaabp.email import send_email_message
from profiles.models import Profile

district = District.objects.get(name="District 3")
profiles = Profile.objects.filter(location__within=district.mpoly)

events = ScheduledEvent.objects.filter(
    Q(slug__contains="d3") | Q(slug__contains="district-3") | Q(slug__contains="westsw-philly")
)
sign_ins = EventSignIn.objects.filter(event__in=events)

SENT = []


class Command(BaseCommand):
    def handle(*args, **kwargs):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "d3-nudge",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name},
                    reply_to=["district3@bikeaction.org"],
                )
                SENT.append(profile.user.email.lower())
            else:
                print(f"skipping {profile}")
        for sign_in in sign_ins:
            if sign_in.email and sign_in.email.lower() not in SENT:
                send_email_message(
                    "d3-nudge",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [sign_in.email],
                    {"first_name": sign_in.first_name},
                    reply_to=["district3@bikeaction.org"],
                )
                SENT.append(profile.user.email.lower())
            else:
                print(f"skipping {sign_in}")

        print(len(SENT))
