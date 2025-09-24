from django.conf import settings
from django.core.management.base import BaseCommand

from campaigns.models import PetitionSignature
from facets.models import District
from pbaabp.email import send_email_message

signatures = PetitionSignature.objects.filter(petition__title="Save the 3rd Street Bike Lane!")
profiles = District.objects.get(name="District 1").contained_profiles.all()

SENT = []


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        print("Petitions!")
        for signature in signatures:
            if signature.email not in SENT:
                send_email_message(
                    "3rd_st_hearing",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [signature.email],
                    {"first_name": signature.first_name, "petition": True},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(signature.email)
            else:
                print(f"skipping {signature}")
        print(len(SENT))
        print("Profiles!")
        for profile in profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "3rd_st_hearing",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
