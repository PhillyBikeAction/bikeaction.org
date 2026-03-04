import secrets
import uuid

from django.contrib.auth import get_user_model
from django.contrib.gis.db import models
from django.contrib.sessions.base_session import AbstractBaseSession
from django.utils.safestring import mark_safe

User = get_user_model()


class LazerSession(AbstractBaseSession):
    """
    Separate session model for Lazer app.
    These sessions are only valid for Lazer API routes and have a longer expiry (1 year).
    """

    class Meta:
        db_table = "lazer_session"

    @classmethod
    def get_session_store_class(cls):
        from lazer.session_backend import SessionStore

        return SessionStore


def generate_share_token():
    return secrets.token_urlsafe(32)


class ViolationSubmission(models.Model):
    submission_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    captured_at = models.DateTimeField(db_index=True)
    location = models.PointField(srid=4326)
    image = models.ImageField(upload_to="lazer/violations")
    plate_recognizer_response = models.JSONField(null=True, blank=True)

    def image_tag_no_href(self):
        return mark_safe('<img src="%s" style="max-height: 50px;"/>' % (self.image.url,))

    def image_tag(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.image.url, self.image.url)
        )


def report_image_upload_to(instance, filename):
    return f"lazer/reports/{instance.submission.submission_id}/{filename}"


class ViolationReport(models.Model):
    submission = models.ForeignKey(ViolationSubmission, on_delete=models.CASCADE)

    date_observed = models.CharField()
    time_observed = models.CharField()

    make = models.CharField()
    model = models.CharField(null=True, blank=True)
    body_style = models.CharField()
    vehicle_color = models.CharField()

    violation_observed = models.CharField(db_index=True)
    occurrence_frequency = models.CharField()

    block_number = models.CharField()
    street_name = models.CharField()
    zip_code = models.CharField()

    additional_information = models.CharField(null=True, blank=True)

    redacted_image = models.ImageField(null=True, blank=True, upload_to=report_image_upload_to)

    submitted = models.DateTimeField(null=True, blank=True)
    service_id = models.CharField(null=True, blank=True)
    submission_response = models.JSONField(null=True, blank=True)

    def is_submitted(self):
        return self.submitted is not None

    is_submitted.boolean = True

    def created_by(self):
        return self.submission.created_by

    def image_tag_violation_no_href(self):
        return mark_safe('<img src="%s" style="max-height: 50px;"/>' % (self.submission.image.url,))

    image_tag_violation_no_href.short_description = "Image"

    def violation_observed_short(self):
        return self.violation_observed.split(" (")[0]

    violation_observed_short.short_description = "Violation"

    def image_tag_violation(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.submission.image.url, self.submission.image.url)
        )

    def image_tag_before_submit(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_before_submit.url, self.screenshot_before_submit.url)
        )

    def image_tag_after_submit(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_after_submit.url, self.screenshot_after_submit.url)
        )

    def image_tag_success(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_success.url, self.screenshot_success.url)
        )

    def image_tag_error(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_error.url, self.screenshot_error.url)
        )

    def image_tag_final(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_final.url, self.screenshot_final.url)
        )

    def image_tag_redacted(self):
        if not self.redacted_image:
            return "-"
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.redacted_image.url, self.redacted_image.url)
        )

    image_tag_redacted.short_description = "Redacted Image"


class LazerWrapped(models.Model):
    """Shareable year-in-review statistics for Laser Vision users."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="lazer_wrapped")
    share_token = models.CharField(
        max_length=64, unique=True, db_index=True, default=generate_share_token
    )

    # Date range for the wrapped report
    year = models.IntegerField()

    # Cached statistics
    total_submissions = models.IntegerField(default=0)
    total_reports = models.IntegerField(default=0)
    violations_by_type = models.JSONField(default=dict)
    top_streets = models.JSONField(default=list)
    top_zip_codes = models.JSONField(default=list)
    reports_by_month = models.JSONField(default=dict)
    first_report_date = models.DateField(null=True, blank=True)
    longest_streak = models.IntegerField(default=0)
    longest_streak_start = models.DateField(null=True, blank=True)
    longest_streak_end = models.DateField(null=True, blank=True)
    longest_streak_reports = models.IntegerField(default=0)
    top_day_date = models.DateField(null=True, blank=True)
    top_day_count = models.IntegerField(default=0)

    # Vehicle make/model stats
    top_user_vehicles = models.JSONField(default=list)
    top_community_vehicles = models.JSONField(default=list)

    # Community comparison stats
    rank = models.IntegerField(null=True, blank=True)
    total_users = models.IntegerField(null=True, blank=True)
    percentile = models.IntegerField(null=True, blank=True)
    avg_reports = models.FloatField(null=True, blank=True)
    total_community_reports = models.IntegerField(null=True, blank=True)
    percent_of_total = models.FloatField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-created_at"]
        unique_together = ["user", "year"]

    def __str__(self):
        return f"{self.user.email} - {self.year} Wrapped"

    def get_share_url(self):
        from django.conf import settings

        return f"{settings.SITE_URL}/tools/laser/wrapped/{self.share_token}/"


class Banner(models.Model):
    """Configurable banner displayed at the top of the Lazer app."""

    COLOR_CHOICES = [
        ("pink", "Pink"),
        ("green", "Green"),
    ]

    content = models.TextField(help_text="Markdown content (supports links)")
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default="green")
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Banner"
        verbose_name_plural = "Banners"

    def __str__(self):
        return f"{self.content[:50]}..." if len(self.content) > 50 else self.content

    def content_html(self):
        """Render markdown content to HTML."""
        import markdown

        return markdown.markdown(self.content)
