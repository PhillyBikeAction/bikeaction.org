import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify


def get_user_display_name(user):
    """
    Get safe public display name for a user.
    Returns first name + last initial only.
    NEVER returns full last name, email, or discord handle.
    """
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    last_initial = f"{last_name[0]}." if last_name else ""
    return f"{first_name} {last_initial}".strip() or user.username


class Election(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    membership_eligibility_deadline = models.DateTimeField(
        help_text="Deadline for membership eligibility to vote"
    )
    nominations_open = models.DateTimeField(help_text="When nominations open")
    nominations_close = models.DateTimeField(help_text="When nominations close")
    voting_opens = models.DateTimeField(help_text="When voting opens")
    voting_closes = models.DateTimeField(help_text="When voting closes")

    # District seat configuration
    at_large_seats_count = models.IntegerField(default=5, help_text="Number of at-large seats")
    district_seat_min_votes = models.IntegerField(
        default=5,
        help_text="Minimum votes from district members required to win district seat",
    )
    district_seat_min_voters = models.IntegerField(
        default=5,
        help_text="Minimum voters in a district required to activate that district's seat",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_upcoming(cls):
        """
        Get the next upcoming election where the membership eligibility deadline hasn't passed.
        Returns None if no upcoming elections.
        """
        return (
            cls.objects.filter(membership_eligibility_deadline__gte=timezone.now())
            .order_by("membership_eligibility_deadline")
            .first()
        )

    def get_eligible_voters(self):
        """
        Get a QuerySet of profiles for users who were eligible voters as of the
        membership eligibility deadline.

        A user is eligible if they meet any of the membership criteria:
        - Active Membership record
        - Discord activity within 30 days (before deadline)
        - Active Stripe subscription
        """
        from datetime import timedelta

        from django.db.models import Q

        from profiles.models import Profile

        # Use the deadline as a single point in time (already a timezone-aware datetime)
        deadline = self.membership_eligibility_deadline
        deadline_date = deadline.date()

        # Calculate Discord activity window (30 days before deadline)
        # Use date arithmetic to avoid timezone conversion issues
        discord_start_date = deadline_date - timedelta(days=30)

        # Build query for users who were members as of the deadline
        # 1. Explicit Membership record active on deadline
        membership_record_query = Q(memberships__start_date__lte=deadline) & (
            Q(memberships__end_date__isnull=True) | Q(memberships__end_date__gte=deadline)
        )

        # 2. Discord activity within 30 days before deadline
        # User must have BOTH a linked Discord account AND recent activity
        # Use date comparison since DiscordActivity.date is a DateField
        discord_activity_query = Q(socialaccount__provider="discord") & Q(
            profile__discord_activity__date__gte=discord_start_date,
            profile__discord_activity__date__lte=deadline_date,
        )

        # 3. Stripe subscription active as of deadline
        # We need to check BOTH:
        # a) Historical invoices (for past billing periods that have ended)
        # b) Current subscription periods (for ongoing subscriptions without invoices yet)
        # This is because invoices are only created after a billing period ends
        deadline_start = deadline.replace(hour=0, minute=0, second=0, microsecond=0)
        deadline_end = deadline.replace(hour=23, minute=59, second=59, microsecond=999999)

        stripe_invoice_query = Q(
            djstripe_customers__subscriptions__invoices__period_start__lte=deadline_end,
            djstripe_customers__subscriptions__invoices__period_end__gte=deadline_start,
            djstripe_customers__subscriptions__invoices__status="paid",
        )
        stripe_current_period_query = Q(
            djstripe_customers__subscriptions__current_period_start__lte=deadline_end,
            djstripe_customers__subscriptions__current_period_end__gte=deadline_start,
        )
        stripe_subscription_query = stripe_invoice_query | stripe_current_period_query

        # Combine all three criteria with OR
        eligible_users_query = (
            membership_record_query | discord_activity_query | stripe_subscription_query
        )

        # Get profiles for eligible users
        return (
            Profile.objects.filter(user__in=User.objects.filter(eligible_users_query))
            .select_related("user")
            .distinct()
        )

    def is_nominations_open(self):
        """Check if nominations are currently open."""
        now = timezone.now()
        return self.nominations_open <= now < self.nominations_close

    def is_nominations_closed(self):
        """Check if nominations have closed."""
        return timezone.now() >= self.nominations_close

    def is_acceptance_period_closed(self):
        """Check if the acceptance period has closed (24 hours after nominations close)."""
        import datetime

        acceptance_deadline = self.nominations_close + datetime.timedelta(hours=24)
        return timezone.now() >= acceptance_deadline

    def is_voting_open(self):
        """Check if voting is currently open."""
        now = timezone.now()
        return self.voting_opens <= now < self.voting_closes

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Nominee(models.Model):
    """
    Represents a person who has been nominated for an election.
    Can have multiple nominations from different nominators.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="nominees")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="nominee_records")

    # Public display information
    photo = models.ImageField(
        upload_to="nominee_photos/",
        blank=True,
        null=True,
        help_text="A headshot, selfie, or even discord profile picture",
    )
    public_display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional, if you go by a different name than you provided on your profile",
    )
    board_responsibilities_acknowledged = models.BooleanField(
        default=False,
        help_text=mark_safe(
            "I have read the <a href='https://docs.google.com/document/d/12DXhkuvArz_efcKpWm1u8HSsMHJVKL18cjvCjtY3r-s/edit?usp=sharing' "
            "target='_blank'>PBA Board "
            "responsibilities and expectations</a>"
        ),
    )

    # Final results (set when election is closed and anonymized)
    final_vote_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total votes received (set when election is closed)",
    )
    final_district_vote_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Votes received from nominee's home district (set when election is closed)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("election", "user")
        ordering = ["-created_at"]

    def __str__(self):
        nominee_name = self.user.get_full_name() or self.user.email
        return f"{nominee_name} for {self.election.title}"

    def nomination_count(self):
        """Return count of non-draft nominations."""
        return self.nominations.filter(draft=False).count()

    def accepted_nomination_count(self):
        """Return count of accepted nominations."""
        return self.nominations.filter(draft=False, acceptance_status="accepted").count()

    def has_accepted_nomination(self):
        """Check if nominee has accepted at least one nomination."""
        return self.nominations.filter(draft=False, acceptance_status="accepted").exists()

    def is_profile_complete(self):
        """Check if nominee profile is complete (has photo and acknowledged responsibilities)."""
        return bool(self.photo) and self.board_responsibilities_acknowledged

    def get_display_name(self):
        """
        Get the public display name for this nominee.
        Returns public_display_name if set, otherwise first name + last initial.
        NEVER returns full last name, email, or discord handle.
        """
        if self.public_display_name:
            return self.public_display_name

        first_name = self.user.first_name or ""
        last_name = self.user.last_name or ""
        last_initial = f"{last_name[0]}." if last_name else ""
        return f"{first_name} {last_initial}".strip()

    def get_slug(self):
        """
        Generate a URL-safe slug for the nominee based on first name + last initial.
        Format: firstname-l
        """
        from django.utils.text import slugify

        first_name = self.user.first_name or ""
        last_name = self.user.last_name or ""
        last_initial = last_name[0].lower() if last_name else ""

        if self.public_display_name:
            return slugify(self.public_display_name)

        return slugify(f"{first_name}-{last_initial}")

    def send_notification_email(self, nomination):
        """Send email notification to nominee for a specific nomination."""
        from django.db import transaction

        from elections.tasks import send_nomination_notification

        transaction.on_commit(lambda: send_nomination_notification.delay(str(nomination.id)))


class Nomination(models.Model):
    """
    Represents a single nomination of a person for an election.
    Multiple people can nominate the same Nominee.
    """

    class AcceptanceStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nominee = models.ForeignKey(Nominee, on_delete=models.CASCADE, related_name="nominations")
    nominator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="nominations_given")

    # Nomination statement
    nomination_statement = models.TextField(
        help_text="Why are you nominating this person?", blank=True, default=""
    )

    # Draft support
    draft = models.BooleanField(default=False)

    # Acceptance tracking (nominee's response to this specific nomination)
    acceptance_status = models.CharField(
        max_length=20,
        choices=AcceptanceStatus.choices,
        default=AcceptanceStatus.PENDING,
    )
    acceptance_date = models.DateTimeField(null=True, blank=True)
    acceptance_note = models.TextField(
        blank=True, null=True, help_text="Optional note from nominee about their decision"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("nominee", "nominator")
        ordering = ["-created_at"]

    def __str__(self):
        nominee_name = self.nominee.user.get_full_name() or self.nominee.user.email
        nominator_name = self.nominator.get_full_name() or self.nominator.email
        status = " (Draft)" if self.draft else f" ({self.get_acceptance_status_display()})"
        return f"{nominee_name} nominated by {nominator_name}{status}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        was_draft = False
        is_self_nomination = self.nominator == self.nominee.user

        if not is_new:
            try:
                old_instance = Nomination.objects.get(pk=self.pk)
                was_draft = old_instance.draft
            except Nomination.DoesNotExist:
                pass

        # Auto-accept self-nominations
        if not self.draft and is_self_nomination and (is_new or was_draft):
            if self.acceptance_status == Nomination.AcceptanceStatus.PENDING:
                self.acceptance_status = Nomination.AcceptanceStatus.ACCEPTED
                self.acceptance_date = timezone.now()

        super().save(*args, **kwargs)

        # Send email notification for new non-draft nominations (but skip self-nominations)
        if not self.draft and (is_new or was_draft) and not is_self_nomination:
            self.nominee.send_notification_email(self)


class Question(models.Model):
    """
    Represents a yes/no question attached to an election ballot.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="questions")
    question_text = models.TextField(help_text="The question to ask voters")
    description = models.TextField(
        blank=True, default="", help_text="Optional description or context for the question"
    )
    order = models.IntegerField(default=0, help_text="Display order (lower numbers appear first)")

    # Final results (set when election is closed and anonymized)
    final_yes_votes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total yes votes (set when election is closed)",
    )
    final_no_votes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total no votes (set when election is closed)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        unique_together = ("election", "order")

    def __str__(self):
        return f"{self.election.title}: {self.question_text[:50]}"


class Ballot(models.Model):
    """
    Represents a user's ballot for an election.
    Contains all votes for candidates and questions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="ballots")
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ballots")

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Track whether ballot had any votes (for turnout calculation after anonymization)
    had_votes = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether this ballot had at least one vote (set when election is closed)",
    )

    class Meta:
        unique_together = ("election", "voter")
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["election", "-submitted_at"]),
        ]

    def __str__(self):
        voter_name = self.voter.get_full_name() or self.voter.email
        return f"{voter_name}'s ballot for {self.election.title}"

    def get_candidate_votes(self):
        """Return QuerySet of all candidate votes on this ballot."""
        return self.candidate_votes.select_related("nominee__user")

    def get_question_votes(self):
        """Return QuerySet of all question votes on this ballot."""
        return self.question_votes.select_related("question")


class Vote(models.Model):
    """
    Represents an approval vote for a candidate on a ballot.
    """

    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, related_name="candidate_votes")
    nominee = models.ForeignKey(Nominee, on_delete=models.CASCADE, related_name="votes")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("ballot", "nominee")
        indexes = [
            models.Index(fields=["ballot"]),
            models.Index(fields=["nominee"]),
        ]

    def __str__(self):
        return f"Vote for {self.nominee.get_display_name()} on ballot {self.ballot.id}"


class QuestionVote(models.Model):
    """
    Represents a yes/no vote on a ballot question.
    """

    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, related_name="question_votes")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="votes")
    answer = models.BooleanField(help_text="True = Yes, False = No")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("ballot", "question")

    def __str__(self):
        answer_text = "Yes" if self.answer else "No"
        return f"{answer_text} on question {self.question.id}"
