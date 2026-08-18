from django.contrib.auth.models import User
from django.db import models


class EmailBlastTarget(models.Model):
    created_by = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class EmailBlastTargetNode(models.Model):
    class TargetType(models.TextChoices):
        ALL_PROFILES = "all_profiles", "All profiles"
        DISTRICT = "district", "District"
        RCO = "rco", "Registered Community Organization"
        ZIP_CODE = "zip_code", "Zip Code"
        WARD = "ward", "Ward"
        DIVISION = "division", "Division"
        GEOJSON = "geojson", "GeoJSON boundary"
        PETITION = "petition", "Petition signers"
        EVENT_RSVP = "event_rsvp", "Event RSVPs"
        EVENT_SIGNIN = "event_signin", "Event sign-ins"
        LEGACY = "legacy", "Legacy/custom targeting"
        VOLUNTEERS = "volunteers", "Volunteering Opt Ins"

    class Operator(models.TextChoices):
        AND = "and", "All of these"
        OR = "or", "Any of these"

    target = models.ForeignKey(
        EmailBlastTarget, blank=True, null=True, on_delete=models.CASCADE, related_name="nodes"
    )
    parent = models.ForeignKey(
        "self", blank=True, null=True, on_delete=models.CASCADE, related_name="children"
    )
    created_by = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    operator = models.CharField(max_length=8, blank=True, choices=Operator.choices)
    primitive_type = models.CharField(max_length=32, blank=True, choices=TargetType.choices)
    primitive_id = models.CharField(max_length=64, blank=True)
    primitive_name = models.CharField(max_length=255, blank=True)
    primitive_geojson = models.JSONField(blank=True, null=True)
    position = models.PositiveIntegerField(default=0)

    def __str__(self):
        if self.operator:
            return self.get_operator_display()
        return self.primitive_name


class EmailBlast(models.Model):
    TargetType = EmailBlastTargetNode.TargetType

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        REJECTED = "rejected", "Rejected"

    submitter = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    subject = models.CharField(max_length=255)
    body = models.TextField()
    reply_to = models.EmailField()

    target = models.ForeignKey(
        EmailBlastTarget,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="email_blasts",
    )

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )

    def __str__(self):
        return f"{self.subject} ({self.target_name})"

    @property
    def target_name(self):
        if not self.target:
            return "No targets"
        return self.target.name


class EmailBlastImage(models.Model):
    email_blast = models.ForeignKey(
        EmailBlast,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="images",
    )
    created_by = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to="emailblasts/images")
    original_filename = models.CharField(max_length=255, blank=True)

    @property
    def email_src(self):
        return f"media/{self.image.name}"

    def __str__(self):
        return self.original_filename or self.image.name


class EmailBlastDelivery(models.Model):
    email_blast = models.ForeignKey(EmailBlast, on_delete=models.CASCADE, related_name="deliveries")
    profile = models.ForeignKey(
        "profiles.Profile", blank=True, null=True, on_delete=models.SET_NULL
    )
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("email_blast", "email"),
                name="unique_email_blast_delivery_email",
            )
        ]
        verbose_name_plural = "email blast deliveries"

    def __str__(self):
        return f"{self.email_blast}: {self.email}"
