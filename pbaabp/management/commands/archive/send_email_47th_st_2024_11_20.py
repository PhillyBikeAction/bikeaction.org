from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from campaigns.models import PetitionSignature
from pbaabp.email import send_email_message
from profiles.models import Profile

TO = ["bikes@durbin.ee"]

signatures = PetitionSignature.objects.filter(
    petition__title="Parking-Protected Bike Lane on 47th St"
).filter(Q(zip_code__startswith="19143") | Q(zip_code__startswith="19104"))
profiles = Profile.objects.filter(zip_code__in=["19143", "19104"])

signatures = []
profiles = Profile.objects.filter(user__email__in=TO)

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
                    "47th_st_2024_11_20",
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
                    "47th_st_2024_11_20",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"first_name": profile.user.first_name},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
