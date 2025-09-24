from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from facets.models import District
from pbaabp.email import send_email_message
from profiles.models import Profile

district1 = District.objects.get(name="District 1")
district2 = District.objects.get(name="District 2")


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        SENT = []
        settings.EMAIL_SUBJECT_PREFIX = ""
        SENT = []
        for profile in Profile.objects.filter(
            Q(location__within=district1.mpoly) | Q(location__within=district2.mpoly)
        ):
            if profile.user.email not in SENT:
                send_email_message(
                    "sp-postcards",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
