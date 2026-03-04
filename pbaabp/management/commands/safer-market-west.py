from django.core.management.base import BaseCommand

from pbaabp.email import send_email_message
from profiles.models import Profile

SENT = []


class Command(BaseCommand):
    def handle(*args, **kwargs):
        for profile in Profile.objects.all():
            if profile.user.email not in SENT:
                send_email_message(
                    "safer-market-west",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {
                        "first_name": profile.user.first_name,
                    },
                    reply_to=["district3@bikeaction.org"],
                )
                SENT.append(profile.user.email.lower())
            else:
                print(f"skipping {profile}")

        print(f"Sent {len(SENT)}")
