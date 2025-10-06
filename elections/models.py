from django.db import models


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

    def __str__(self):
        return self.title
