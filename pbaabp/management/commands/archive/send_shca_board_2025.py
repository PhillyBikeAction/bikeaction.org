from django.conf import settings
from django.core.management.base import BaseCommand

from facets.models import RegisteredCommunityOrganization
from pbaabp.email import send_email_message

_rco = RegisteredCommunityOrganization.objects.get(id="49588520-93e1-4d70-ae30-892c1e96610c")


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in _rco.contained_profiles.all():
            send_email_message(
                "shca_board_2025",
                "Philly Bike Action <noreply@bikeaction.org>",
                [profile.user.email],
                {"first_name": profile.user.first_name},
                reply_to=["district1@bikeaction.org"],
            )
