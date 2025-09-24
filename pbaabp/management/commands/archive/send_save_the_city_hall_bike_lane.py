import hashlib

from django.conf import settings
from django.core.management.base import BaseCommand

from campaigns.models import Petition
from facets.models import District
from pbaabp.email import send_email_message

signatures = Petition.objects.get(slug="build-the-city-hall-bike-lane").signatures.all()
DONOTSEND = [
    "0bea71a0f2e322129b48711357afabade802140ecb1f7b72828ea010665ab63f",
    "21d070a8020f0e3b90b2a2e3162128759019271bdee530f7acfb345bc7719d0b",
]

SENT = []


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for signature in signatures:
            if hashlib.sha256(signature.email.encode()).hexdigest() in DONOTSEND:
                print(f"skipping {signature} - DONOTSEND")
                continue
            if signature.email in SENT:
                print(f"skipping {signature} - DUPLICATE")
                continue
            if signature.location is None:
                print(f"skipping {signature} - NOGEOLOCATION")
                continue
            if District.objects.filter(mpoly__contains=signature.location).first() is None:
                print(f"skipping {signature} - NOT PHILLY")
                continue
            send_email_message(
                "save-the-city-hall-bike-lane",
                "Philly Bike Action <noreply@bikeaction.org>",
                [signature.email],
                {"first_name": signature.first_name},
                reply_to=["info@bikeaction.org"],
            )
            SENT.append(signature.email)
        print(len(SENT))
