import uuid

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django_jsonform.models.fields import JSONField
from markdownfield.models import RenderedMarkdownField
from markdownfield.validators import VALIDATOR_NULL
from multi_email_field.fields import MultiEmailField

from events.models import ScheduledEvent
from pbaabp.models import ChoiceArrayField, MarkdownField


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        COMPLETED = "completed"
        CANCELED = "canceled"
        SUSPENDED = "suspended"
        UNKNOWN = "unknown"

    class District(models.IntegerChoices):
        NO_DISTRICT = 0, "N/A - Not Philadelphia"
        DISTRICT_1 = 1, "District 1"
        DISTRICT_2 = 2, "District 2"
        DISTRICT_3 = 3, "District 3"
        DISTRICT_4 = 4, "District 4"
        DISTRICT_5 = 5, "District 5"
        DISTRICT_6 = 6, "District 6"
        DISTRICT_7 = 7, "District 7"
        DISTRICT_8 = 8, "District 8"
        DISTRICT_9 = 9, "District 9"
        DISTRICT_10 = 10, "District 10"
        ALL_CITY = 99, "All of Philadelphia"

    TAGS_SCHEMA = {"type": "array", "items": {"type": "string"}}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=512)
    slug = models.SlugField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    description = models.TextField(null=True, blank=True)
    cover = models.ImageField(upload_to="campaigns", null=True, blank=True)

    donation_action = models.BooleanField(default=False)
    subscription_action = models.BooleanField(default=False)

    newsletter_action = models.BooleanField(default=False)
    newsletter_cta = models.TextField(null=True, blank=True)
    newsletter_tags = JSONField(schema=TAGS_SCHEMA, null=True, blank=True)

    content = MarkdownField(rendered_field="content_rendered", validator=VALIDATOR_NULL)
    content_rendered = RenderedMarkdownField()

    wordpress_id = models.CharField(max_length=64, null=True, blank=True)

    events = models.ManyToManyField(ScheduledEvent, blank=True, null=True)

    @property
    def has_actions(self):
        return (
            self.petitions.count()
            or self.events.count()
            or self.donation_action
            or self.subscription_action
        )

    def future_events(self):
        return self.events.filter(start_datetime__gt=timezone.now())

    def save(self, *args, **kwargs):
        if self.slug is None:
            self.slug = slugify(self.title)[:49]
        super(Campaign, self).save(*args, **kwargs)

    def __str__(self):
        return self.title


class Petition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=512)
    slug = models.SlugField(null=True, blank=True)
    letter = models.TextField()
    call_to_action = models.CharField(
        max_length=64, null=True, blank=True, default="Add your signature to the following message"
    )
    signature_goal = models.IntegerField(default=None, null=True, blank=True)

    send_email = models.BooleanField(default=False, blank=False)
    email_subject = models.CharField(max_length=988, blank=True, null=True)
    email_body = models.TextField(null=True, blank=True)
    email_to = MultiEmailField(blank=True, null=True)
    email_cc = MultiEmailField(blank=True, null=True)
    email_include_comment = models.BooleanField(default=False)

    campaign = models.ForeignKey(
        Campaign,
        null=True,
        blank=True,
        to_field="id",
        on_delete=models.CASCADE,
        related_name="petitions",
    )

    class PetitionSignatureChoices(models.TextChoices):
        FIRST_NAME = "first_name", "First Name"
        LAST_NAME = "last_name", "Last Name"
        EMAIL = "email", "E-mail"
        ADDRESS_LINE_1 = "postal_address_line_1", "Address Line 1"
        ADDRESS_LINE_2 = "postal_address_line_2", "Address Line 2"
        CITY = "city", "City"
        STATE = "state", "State"
        ZIP_CODE = "zip_code", "Zip Code"
        COMMENT = "comment", "Comment"

    signature_fields = ChoiceArrayField(
        models.CharField(
            max_length=128, null=True, blank=True, choices=PetitionSignatureChoices.choices
        ),
        blank=True,
        null=True,
    )

    def save(self, *args, **kwargs):
        if self.slug is None:
            self.slug = slugify(self.title)[:49]
        super(Petition, self).save(*args, **kwargs)

    def form(self):
        from campaigns.forms import PetitionSignatureForm

        form = PetitionSignatureForm(petition=self)
        return form

    def signatures_with_comment(self):
        return self.signatures.filter(comment__isnull=False).exclude(comment="").all()

    def distinct_signatures_with_comment(self):
        return (
            self.signatures.distinct("email")
            .filter(comment__isnull=False)
            .exclude(comment="")
            .all()
        )

    @property
    def comments(self):
        return self.signatures.filter(comment__isnull=False).exclude(comment="").count()

    @property
    def progress(self):
        if self.signature_goal:
            if self.signatures.count() > self.signature_goal:
                return 100
            return int(100 * (self.signatures.count() / self.signature_goal))
        return 100

    def __str__(self):
        return self.title


class PetitionSignature(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    petition = models.ForeignKey(
        Petition, to_field="id", on_delete=models.CASCADE, related_name="signatures"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    featured = models.BooleanField(default=False)
    visible = models.BooleanField(default=True)

    comment = models.TextField(null=True, blank=True)
    first_name = models.CharField(max_length=64, null=True, blank=True)
    last_name = models.CharField(max_length=64, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    postal_address_line_1 = models.CharField(
        verbose_name="Address line 1", max_length=128, null=True, blank=True
    )
    postal_address_line_2 = models.CharField(
        verbose_name="Address line 2", max_length=128, null=True, blank=True
    )
    city = models.CharField(verbose_name="City", max_length=64, null=True, blank=True)
    state = models.CharField(verbose_name="State", max_length=64, null=True, blank=True)
    zip_code = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^(^[0-9]{5}(?:-[0-9]{4})?$|^$)",
                message="Must be a valid zipcode in formats 19107 or 19107-3200",
            )
        ],
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"
