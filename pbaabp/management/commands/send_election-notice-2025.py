from django.core.management.base import BaseCommand

from elections.models import Election
from pbaabp.email import send_email_message

SENT = []


class Command(BaseCommand):
    def handle(*args, **kwargs):
        # Get the current/upcoming election (where voting hasn't closed yet)
        from django.utils import timezone

        election = (
            Election.objects.filter(voting_closes__gte=timezone.now())
            .order_by("voting_closes")
            .first()
        )
        if not election:
            print("No current or upcoming election found")
            return

        print(f"Sending election notice for: {election.title}")
        print(f"Membership eligibility deadline: {election.membership_eligibility_deadline}")

        # Get eligible voters for this election
        eligible_profiles = election.get_eligible_voters()
        print(f"Found {eligible_profiles.count()} eligible voters")

        for profile in eligible_profiles:
            if profile.user.email not in SENT:
                send_email_message(
                    "election-notice-2025",
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
