from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from facets.models import RegisteredCommunityOrganization
from pbaabp.email import send_email_message

SENT = []

profiles = set()
for rco in RegisteredCommunityOrganization.objects.filter(
    Q(name="Queen Village Neighbors Association") | Q(name="Bella Vista Neighbors Association")
).all():
    profiles.update(set(rco.contained_profiles.all()))


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "6th-n-pass",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
