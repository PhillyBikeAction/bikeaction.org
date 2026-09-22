from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from pbaabp.email import send_email_message
from profiles.models import DoNotEmail
from profiles.signals import ORGANIZER_GROUP_NAME


class Command(BaseCommand):
    def handle(self, *args, **options):
        users = (
            get_user_model()
            .objects.filter(groups__name=ORGANIZER_GROUP_NAME)
            .exclude(email="")
            .order_by("pk")
            .distinct()
        )
        blocked = {email.casefold() for email in DoNotEmail.objects.values_list("email", flat=True)}
        seen = set()
        count = 0

        for user in users:
            email = user.email.strip()
            key = email.casefold()
            if not email or key in blocked or key in seen:
                continue
            seen.add(key)

            send_email_message(
                "organizer-test",
                None,
                [email],
                {"user": user, "first_name": user.first_name},
                reply_to=["info@bikeaction.org"],
            )
            self.stdout.write(f"Sent to: {email}")
            count += 1

        self.stdout.write(self.style.SUCCESS(f"{count} email(s)."))
