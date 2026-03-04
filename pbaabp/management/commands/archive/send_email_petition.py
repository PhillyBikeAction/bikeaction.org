from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from campaigns.models import PetitionSignature
from facets.models import RegisteredCommunityOrganization
from facets.utils import geocode_address
from pbaabp.email import send_email_message

_rco = RegisteredCommunityOrganization.objects.get(id="0ea45345-e81e-47a0-8312-b2190e064e2d")
_signatures = PetitionSignature.objects.filter(
    petition__id__in=[
        "f92963b4-c2ff-4096-9da6-0ac86eb61ff9",
        "658754c6-9db0-4efe-bc32-69652fed9650",
    ]
)
signatures = []
_emails = []
for _signature in _signatures:
    print(f"geocoding {_signature}")
    address = async_to_sync(geocode_address)(
        f"{_signature.postal_address_line_1} {_signature.city}, {_signature.state}"
    )
    if (
        _rco.mpoly.contains(Point(address.longitude, address.latitude))
        and _signature.email not in _emails
    ):
        signatures.append(_signature)
        _emails.append(_signature.email)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for signature in signatures:
            send_email_message(
                options["email_template"],
                "Philly Bike Action <noreply@bikeaction.org>",
                [signature.email],
                {"signature": signature},
                reply_to=["info@bikeaction.org"],
            )
