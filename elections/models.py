from django.db import models
from django.utils import timezone


class Election(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    membership_eligibility_deadline = models.DateTimeField(
        help_text="Deadline for membership eligibility to vote"
    )
    nominations_open = models.DateTimeField(help_text="When nominations open")
    nominations_close = models.DateTimeField(help_text="When nominations close")
    voting_opens = models.DateTimeField(help_text="When voting opens")
    voting_closes = models.DateTimeField(help_text="When voting closes")

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

    def __str__(self):
        return self.title
