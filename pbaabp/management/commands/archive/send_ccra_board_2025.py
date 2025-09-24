from django.conf import settings
from django.core.management.base import BaseCommand

from facets.models import RegisteredCommunityOrganization
from pbaabp.email import send_email_message

_rco = RegisteredCommunityOrganization.objects.get(id="3a17d622-0517-4161-b33e-efb5fa95ff44")


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in _rco.contained_profiles.all():
            send_email_message(
                "ccra_board_2025",
                "Philly Bike Action <noreply@bikeaction.org>",
                [profile.user.email],
                {"first_name": profile.user.first_name},
                reply_to=["info@bikeaction.org"],
            )
