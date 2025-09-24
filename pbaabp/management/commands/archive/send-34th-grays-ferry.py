from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from facets.models import District
from pbaabp.email import send_email_message
from profiles.models import Profile

district3 = District.objects.get(name="District 3")
district2 = District.objects.get(name="District 2")


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        SENT = []
        for profile in Profile.objects.filter(
            Q(location__within=district2.mpoly) | Q(location__within=district3.mpoly)
        ):
            if profile.user.email not in SENT:
                send_email_message(
                    "34th-grays-ferry",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name},
                    reply_to=["district2@bikeaction.org,district3@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
