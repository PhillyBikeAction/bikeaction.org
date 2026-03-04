from django.conf import settings
from django.core.management.base import BaseCommand

from campaigns.models import PetitionSignature
from pbaabp.email import send_email_message

signatures = PetitionSignature.objects.filter(petition__title="Build the City Hall Bike Lane")


class Command(BaseCommand):
    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        SENT = []
        print("Petitions!")
        for signature in signatures:
            if signature.email not in SENT:
                send_email_message(
                    "city-hall-bike-lane-open-house",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [signature.email],
                    {"first_name": signature.first_name, "petition": True},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(signature.email)
            else:
                print(f"skipping {signature}")
        print(len(SENT))
