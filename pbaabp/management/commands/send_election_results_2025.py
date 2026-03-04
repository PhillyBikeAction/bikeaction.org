from django.core.management.base import BaseCommand

from elections.models import Election
from pbaabp.email import send_email_message

SENT = []


class Command(BaseCommand):
    def handle(*args, **kwargs):
        # Get the most recently concluded election (where voting has closed)
        from django.utils import timezone

        election = (
            Election.objects.filter(voting_closes__lt=timezone.now())
            .order_by("-voting_closes")
            .first()
        )
        if not election:
            print("No concluded election found")
            return

        print(f"Sending election results for: {election.title}")
        print(f"Voting closed: {election.voting_closes}")

        # Get eligible voters for this election
        eligible_profiles = election.get_eligible_voters()
        print(f"Found {eligible_profiles.count()} eligible voters")

        for profile in eligible_profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "election-results-2025",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {
                        "first_name": profile.user.first_name,
                    },
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email.lower())
            else:
                print(f"skipping {profile}")

        print(f"Sent {len(SENT)}")
