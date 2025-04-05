import uuid

from django.contrib.gis.db import models
from django.core.validators import RegexValidator
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from markdownfield.models import RenderedMarkdownField
from markdownfield.validators import VALIDATOR_NULL
from ordered_model.models import OrderedModel

from events.models import ScheduledEvent
from facets.models import District, RegisteredCommunityOrganization
from lib.slugify import unique_slugify
from membership.models import Donation, DonationProduct
from pbaabp.models import ChoiceArrayField, MarkdownField
from pbaabp.tasks import create_pba_account, subscribe_to_newsletter


class Campaign(OrderedModel):
    class Status(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        COMPLETED = "completed"
        CANCELED = "canceled"
        SUSPENDED = "suspended"
        UNKNOWN = "unknown"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    title = models.CharField(max_length=512)
    slug = models.SlugField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    visible = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True)
    cover = models.ImageField(upload_to="campaigns", null=True, blank=True)
    call_to_action = models.CharField(max_length=64, null=True, blank=True)
    call_to_action_header = models.BooleanField(default=True)

    donation_action = models.BooleanField(default=False)
    donation_product = models.ForeignKey(
        DonationProduct,
        null=True,
        blank=True,
        to_field="id",
        on_delete=models.SET_NULL,
        related_name="campaigns",
    )
    donation_goal = models.IntegerField(default=None, null=True, blank=True)
    donation_goal_show_numbers = models.BooleanField(default=True)

    subscription_action = models.BooleanField(default=False)

    social_shares = models.BooleanField(default=True)

    content = MarkdownField(rendered_field="content_rendered", validator=VALIDATOR_NULL)
    content_rendered = RenderedMarkdownField()

    wordpress_id = models.CharField(max_length=64, null=True, blank=True)

    events = models.ManyToManyField(ScheduledEvent, blank=True, null=True)

    districts = models.ManyToManyField(District, related_name="+", null=True, blank=True)
    registered_community_organizations = models.ManyToManyField(
        RegisteredCommunityOrganization, related_name="+", null=True, blank=True
    )

    @property
    def has_actions(self):
        return (
            self.petitions.filter(display_on_campaign_page=True).count()
            or self.events.count()
            or self.donation_action
            or self.subscription_action
        )

    @property
    def donation_total(self):
        if self.donation_product:
            return Donation.objects.filter(donation_product=self.donation_product).aggregate(
                models.Sum("amount", default=0)
            )["amount__sum"]
        return None

    @property
    def donation_progress(self):
        if self.donation_goal:
            if self.donation_total > self.donation_goal:
                return 100
            return int(100 * (self.donation_total / self.donation_goal))
        return 100

    def future_events(self):
        return self.events.filter(start_datetime__gt=timezone.now())

    def save(self, *args, **kwargs):
        if self.slug is None:
            unique_slugify(self, self.title)
        super(Campaign, self).save(*args, **kwargs)

    def __str__(self):
        return self.title


class Petition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=512)
    slug = models.SlugField(null=True, blank=True)
    letter = models.TextField(null=True, blank=True)
    call_to_action = models.CharField(
        max_length=64, null=True, blank=True, default="Add your signature to the following message"
    )
    call_to_action_header = models.BooleanField(default=True)
    display_on_campaign_page = models.BooleanField(default=True, blank=False)
    signature_goal = models.IntegerField(default=None, null=True, blank=True)
    show_submissions = models.BooleanField(default=True)

    mailto_send = models.BooleanField(default=False, blank=False)
    send_email = models.BooleanField(default=False, blank=False)
    email_subject = models.CharField(max_length=988, blank=True, null=True)
    email_body = models.TextField(null=True, blank=True)
    email_to = models.TextField(blank=True, null=True, help_text="one per line")
    email_cc = models.TextField(blank=True, null=True, help_text="one per line")
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
        PHONE = "phone_number", "Phone Number"
        ADDRESS_LINE_1 = "postal_address_line_1", "Street Address"
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

    create_account_opt_in = models.BooleanField(default=False, blank=False)

    def save(self, *args, **kwargs):
        if self.slug is None:
            unique_slugify(self, self.title)
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
    phone_number = models.CharField(
        max_length=17,
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$",
                message=(
                    "Phone number must be entered in the format: "
                    "'+999999999'. Up to 15 digits allowed."
                ),
            )
        ],
        null=True,
        blank=True,
    )
    postal_address_line_1 = models.CharField(
        verbose_name="Street Address", max_length=128, null=True, blank=True
    )
    postal_address_line_2 = models.CharField(
        verbose_name="Address Line 2", max_length=128, null=True, blank=True
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
    location = models.PointField(blank=True, null=True, srid=4326)

    newsletter_opt_in = models.BooleanField(
        blank=False, default=True, verbose_name=_("Newsletter Opt-In")
    )
    create_account_opt_in = models.BooleanField(
        blank=False, default=False, verbose_name=_("Create a PBA Account")
    )

    def save(self, *args, **kwargs):
        if self.email and self.newsletter_opt_in:
            name = ""
            if self.first_name:
                name += self.first_name
            if self.last_name:
                name += f" {self.last_name}"
            transaction.on_commit(
                lambda: subscribe_to_newsletter.delay(
                    self.email,
                    name,
                    tags=["petition", f"petition-{self.petition.slug}"],
                )
            )
        if self.create_account_opt_in:
            transaction.on_commit(
                lambda: create_pba_account.delay(
                    first_name=self.first_name,
                    last_name=self.last_name,
                    street_address=self.postal_address_line_1,
                    zip_code=self.zip_code,
                    email=self.email,
                    newsletter_opt_in=self.newsletter_opt_in,
                )
            )
        super(PetitionSignature, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"
