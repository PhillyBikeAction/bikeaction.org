"""
Management command to simulate voter turnout for an election.

Usage:
    ./manage.py simulate_voters --election-slug <slug> --turnout 0.69 --approval-rate 0.75
"""

import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from elections.models import Ballot, Election, Nomination, Nominee, QuestionVote, Vote


class Command(BaseCommand):
    help = "Simulate voter turnout for an election"

    def add_arguments(self, parser):
        parser.add_argument(
            "--election-slug",
            type=str,
            help="Slug of the election to simulate (defaults to first election)",
        )
        parser.add_argument(
            "--turnout",
            type=float,
            default=0.69,
            help="Voter turnout rate (0.0 to 1.0, default: 0.69)",
        )
        parser.add_argument(
            "--approval-rate",
            type=float,
            default=0.75,
            help="Average approval rate for candidates (0.0 to 1.0, default: 0.75)",
        )
        parser.add_argument(
            "--yes-rate",
            type=float,
            default=0.5,
            help="Probability of voting Yes on questions (0.0 to 1.0, default: 0.5)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing ballots before simulating",
        )

    def handle(self, *args, **options):
        # Safety check: only allow in DEBUG mode
        if not settings.DEBUG:
            raise CommandError(
                "This command can only be run with DEBUG=True. "
                "Refusing to simulate voters in production environment."
            )

        # Get election
        if options["election_slug"]:
            try:
                election = Election.objects.get(slug=options["election_slug"])
            except Election.DoesNotExist:
                raise CommandError(f"Election with slug '{options['election_slug']}' not found")
        else:
            election = Election.objects.first()
            if not election:
                raise CommandError("No elections found")

        turnout_rate = options["turnout"]
        approval_rate = options["approval_rate"]
        yes_rate = options["yes_rate"]

        # Validate parameters
        if not 0 <= turnout_rate <= 1:
            raise CommandError("Turnout rate must be between 0 and 1")
        if not 0 <= approval_rate <= 1:
            raise CommandError("Approval rate must be between 0 and 1")
        if not 0 <= yes_rate <= 1:
            raise CommandError("Yes rate must be between 0 and 1")

        self.stdout.write(f"Simulating voters for: {election.title}")

        # Get eligible voters
        eligible_voters = list(election.get_eligible_voters())
        self.stdout.write(f"Eligible voters: {len(eligible_voters)}")

        # Get accepted nominees
        nominees = list(
            Nominee.objects.filter(
                election=election,
                nominations__acceptance_status=Nomination.AcceptanceStatus.ACCEPTED,
                nominations__draft=False,
            ).distinct()
        )
        self.stdout.write(f"Accepted nominees: {len(nominees)}")

        # Get questions
        questions = list(election.questions.all())
        self.stdout.write(f"Questions: {len(questions)}")

        # Clear existing ballots if requested
        if options["clear"]:
            existing_count = Ballot.objects.filter(election=election).count()
            if existing_count > 0:
                Ballot.objects.filter(election=election).delete()
                self.stdout.write(self.style.WARNING(f"Cleared {existing_count} existing ballots"))

        # Calculate number of voters
        num_voters = int(len(eligible_voters) * turnout_rate)
        self.stdout.write(f"Simulating {num_voters} voters ({turnout_rate:.1%} turnout)")

        # Randomly select voters
        voters_to_simulate = random.sample(eligible_voters, num_voters)

        # Simulate ballots
        ballots_created = 0
        votes_created = 0
        question_votes_created = 0

        with transaction.atomic():
            for profile in voters_to_simulate:
                user = profile.user

                # Skip if ballot already exists
                if Ballot.objects.filter(election=election, voter=user).exists():
                    continue

                # Create ballot
                ballot = Ballot.objects.create(election=election, voter=user)
                ballots_created += 1

                # Determine how many candidates this voter approves of
                # Use a normal distribution around the approval_rate with some variance
                approval_variance = 0.15
                voter_approval_rate = random.gauss(approval_rate, approval_variance)
                voter_approval_rate = max(0.1, min(1.0, voter_approval_rate))  # Clamp to [0.1, 1.0]

                num_approvals = int(len(nominees) * voter_approval_rate)
                num_approvals = max(1, min(len(nominees), num_approvals))  # At least 1, at most all

                # Randomly select nominees to approve
                approved_nominees = random.sample(nominees, num_approvals)

                # Create votes
                for nominee in approved_nominees:
                    Vote.objects.create(ballot=ballot, nominee=nominee)
                    votes_created += 1

                # Vote on questions
                for question in questions:
                    # Randomly determine Yes or No based on yes_rate
                    answer = random.random() < yes_rate
                    QuestionVote.objects.create(ballot=ballot, question=question, answer=answer)
                    question_votes_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSimulation complete!\n"
                f"  Ballots created: {ballots_created}\n"
                f"  Candidate votes created: {votes_created}\n"
                f"  Question votes created: {question_votes_created}\n"
                f"  Average votes per ballot: {votes_created / ballots_created:.1f}"
            )
        )
