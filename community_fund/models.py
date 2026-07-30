import uuid
from os.path import basename
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from community_fund.forms import CommunityActionFundApplicationForm


def community_action_fund_supporting_material_upload_to(instance, filename):
    project_title = instance.application.data.get("project_title", {}).get("value", "project")
    original_file = Path(filename)
    return (
        "community-fund-supporting-materials/"
        f"{slugify(project_title)}-{slugify(original_file.stem)}-"
        f"{uuid.uuid4().hex[:8]}{original_file.suffix.lower()}"
    )


class CommunityActionFundApplicationPeriod(models.Model):
    name = models.CharField(max_length=128)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ("-starts_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="community_fund_period_ends_after_start",
            )
        ]

    @classmethod
    def applications_are_open(cls):
        now = timezone.now()
        return cls.objects.filter(starts_at__lte=now, ends_at__gte=now).exists()

    def __str__(self):
        return f"{self.name}: {self.starts_at:%b %d, %Y}–{self.ends_at:%b %d, %Y}"


class CommunityActionFundApplication(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submitter = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    draft = models.BooleanField(default=False)
    data = models.JSONField()
    markdown = models.TextField(blank=True)
    thread_id = models.CharField(max_length=64, null=True, blank=True)
    decision = models.CharField(max_length=16, choices=Decision.choices, null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return self.data.get("project_title", {}).get("value", "Community Action Fund application")

    def render_markdown(self):
        self.markdown = render_to_string(
            "community_fund/application.md",
            {
                "application": self,
                "form": CommunityActionFundApplicationForm(label_suffix=""),
                "site_url": settings.SITE_URL.rstrip("/"),
            },
        )

    def save(self, *args, **kwargs):
        if not self.draft and not self.thread_id:
            from community_fund.tasks import add_new_community_action_fund_message_and_thread

            transaction.on_commit(
                lambda: add_new_community_action_fund_message_and_thread.delay(self.id)
            )
        super().save(*args, **kwargs)


class CommunityActionFundSupportingMaterial(models.Model):
    application = models.ForeignKey(
        CommunityActionFundApplication,
        on_delete=models.CASCADE,
        related_name="supporting_materials",
    )
    file = models.FileField(upload_to=community_action_fund_supporting_material_upload_to)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name

    @property
    def filename(self):
        return basename(self.file.name)
