from django.conf import settings
from django.core.management.base import BaseCommand

from facets.models import Ward
from pbaabp.email import send_email_message

_ward = Ward.objects.get(id="cc5193ae-661b-4528-beab-dfb5e8246a2c")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in _ward.contained_profiles.all():
            send_email_message(
                "15th-ward",
                "Philly Bike Action <noreply@bikeaction.org>",
                [profile.user.email],
                {"first_name": profile.user.first_name},
                reply_to=["district5@bikeaction.org"],
            )
