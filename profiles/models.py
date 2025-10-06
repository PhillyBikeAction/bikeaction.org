import datetime
import uuid

from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.validators import RegexValidator
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from facets.models import District as DistrictFacet
from facets.models import (
    RegisteredCommunityOrganization as RegisteredCommunityOrganizationFacet,
)
from organizers.models import OrganizerApplication
from profiles.tasks import geocode_profile, sync_to_mailjet
from projects.models import ProjectApplication


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mailjet_contact_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)

    street_address = models.CharField(
        max_length=256,
        null=True,
        blank=False,
        verbose_name=_("Street Address"),
        help_text=_(
            "Your street address will be used to determine your Philadelphia "
            "City Council District and connect you with actions "
            "you can take in your specific neighborhood."
        ),
    )
    zip_code = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^(^[0-9]{5}(?:-[0-9]{4})?$|^$)",
                message="Must be a valid zipcode in formats 19107 or 19107-3200",
            )
        ],
        null=True,
        blank=False,
        verbose_name=_("Zip Code"),
    )
    newsletter_opt_in = models.BooleanField(
        blank=False,
        default=False,
        verbose_name=_("Newsletter"),
        help_text=_("Subscribe to Philly Bike Actions monthly newsletter."),
    )

    location = models.PointField(blank=True, null=True, srid=4326)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            old_model = Profile.objects.get(pk=self.pk)
            change_fields = [
                f.name
                for f in Profile._meta._get_fields()
                if f.name in ["newsletter_opt_in", "street_address"]
            ]
            modified = False
            for i in change_fields:
                if getattr(old_model, i, None) != getattr(self, i, None):
                    modified = True
            if modified:
                transaction.on_commit(lambda: sync_to_mailjet.delay(self.id))
                transaction.on_commit(lambda: geocode_profile.delay(self.id))
        else:
            transaction.on_commit(lambda: sync_to_mailjet.delay(self.id))
            transaction.on_commit(lambda: geocode_profile.delay(self.id))
        super(Profile, self).save(*args, **kwargs)

    def membership(self):
        return (
            User.objects.filter(id=self.user.id)
            .filter(
                Q(
                    Q(socialaccount__provider="discord")
                    & Q(
                        profile__discord_activity__date__gte=(
                            timezone.now().date() - datetime.timedelta(days=30)
                        )
                    )
                )
                | Q(djstripe_customers__subscriptions__status__in=["active"])
            )
            .exists()
        )

    membership.boolean = True

    def donor(self):
        return (
            User.objects.filter(id=self.user.id)
            .filter(Q(djstripe_customers__subscriptions__status__in=["active"]))
            .exists()
        )

    donor.boolean = True

    def discord_active(self):
        return (
            User.objects.filter(id=self.user.id)
            .filter(
                Q(socialaccount__provider="discord")
                & Q(
                    profile__discord_activity__date__gte=(
                        timezone.now().date() - datetime.timedelta(days=30)
                    )
                )
            )
            .exists()
        )

    discord_active.boolean = True

    def discord_messages_last_30(self):
        from django.db.models import Sum

        thirty_days_ago = timezone.now().date() - datetime.timedelta(days=30)
        total = self.discord_activity.filter(date__gte=thirty_days_ago).aggregate(
            total=Sum("count")
        )["total"]
        return total or 0

    @property
    def complete(self):
        return bool(self.street_address) and bool(self.zip_code)

    @property
    def apps_connected(self):
        return self.discord is not None

    @property
    def project_application_drafts(self):
        return ProjectApplication.objects.filter(submitter=self.user, draft=True).all()

    @property
    def project_applications(self):
        return ProjectApplication.objects.filter(submitter=self.user, draft=False).all()

    @property
    def organizer_application_draft(self):
        return OrganizerApplication.objects.filter(submitter=self.user, draft=True).all()

    @property
    def organizer_application(self):
        return OrganizerApplication.objects.filter(submitter=self.user, draft=False).all()

    @property
    def district(self):
        if self.street_address is None:
            return None
        if self.location is None:
            return None
        return DistrictFacet.objects.filter(mpoly__contains=self.location).first()

    @property
    def rcos(self):
        if self.street_address is None:
            return None
        if self.location is None:
            return None
        return (
            RegisteredCommunityOrganizationFacet.objects.filter(mpoly__contains=self.location)
            .filter(properties__ORG_TYPE="Other")
            .order_by("properties__OBJECTID")
            .all()
        )

    @property
    def ward_rcos(self):
        if self.street_address is None:
            return None
        if self.location is None:
            return None
        return (
            RegisteredCommunityOrganizationFacet.objects.filter(mpoly__contains=self.location)
            .filter(properties__ORG_TYPE="Ward")
            .order_by("properties__OBJECTID")
            .all()
        )

    @property
    def other_rcos(self):
        if self.street_address is None:
            return None
        if self.location is None:
            return None
        return (
            RegisteredCommunityOrganizationFacet.objects.filter(mpoly__contains=self.location)
            .filter(properties__ORG_TYPE__in=["NID", "SSD", None])
            .order_by("properties__OBJECTID")
            .all()
        )

    @property
    def discord(self):
        return self.user.socialaccount_set.filter(provider="discord").first()

    @property
    def events(self):
        return [rsvp.event for rsvp in self.user.event_rsvps.all()]

    @property
    def upcoming_events(self):
        return (
            self.user.event_rsvps.filter(
                event__start_datetime__gte=datetime.datetime.now() - datetime.timedelta(hours=3)
            )
            .order_by("event__start_datetime")
            .all()
        )

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.user.email}"


class DiscordActivity(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="discord_activity")
    date = models.DateField()
    count = models.IntegerField()

    class Meta:
        indexes = [models.Index(fields=["profile", "date"])]


class DoNotEmail(models.Model):
    """
    Model to track email addresses that should not be contacted.
    Used for users who deleted their accounts or explicitly opted out.
    """

    class Reason(models.TextChoices):
        ACCOUNT_DELETION = "account_deletion", "Account Deletion"
        KNOWN_OPPONENT = "known_opponent", "Known Opponent"

    email = models.EmailField(unique=True)
    reason = models.CharField(max_length=50, choices=Reason.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} ({self.get_reason_display()})"

    class Meta:
        verbose_name = "Do Not Email"
        verbose_name_plural = "Do Not Email"


class ShirtOrder(models.Model):
    class ProductType(models.IntegerChoices):
        T_SHIRT = 0, "T-Shirt"
        SWEATSHIRT = 1, "Sweatshirt"

    class Fit(models.IntegerChoices):
        # ALTERNATIVE_01070C = 0, 'Unisex Classic Fit - "Go-To T-Shirt"'
        # ALTERNATIVE_5114C1 = (
        #    1,
        #    "Women's Relaxed Fit - \"Women's Go-To Headliner Cropped Tee\"",
        # )
        NEXT_LEVEL_3600 = 2, 'Unisex Classic Fit - "Next Level - Cotton T-Shirt - 3600"'
        NEXT_LEVEL_1580 = 3, "Women's Relaxed Fit - \"Next Level - Women's Ideal Crop Top - 1580\""
        GILDAN_G180 = 4, 'Unisex Classic Fit - "Gildan G180 - Heavy Blend Crewneck Sweatshirt"'

    class Size(models.IntegerChoices):
        XS = -2, "XS"
        S = -1, "S"
        M = 0, "M"
        L = 1, "L"
        XL = 2, "XL"
        XXL = 3, "2XL"

    class PrintColor(models.IntegerChoices):
        PINK = 0, "Pink"
        GREEN = 1, "Green"

    class ShippingMethod(models.TextChoices):
        USPS = "usps"
        COURIER = "courier"
        PICKUP = "pickup"
        OTHER = "other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tshirt_orders")
    paid = models.BooleanField(default=False)
    fulfilled = models.BooleanField(default=False)
    billing_details = models.JSONField(null=True, blank=True)
    shipping_details = models.JSONField(null=True, blank=True)

    location = models.PointField(blank=True, null=True, srid=4326)
    shipping_method = models.CharField(
        max_length=32, null=True, blank=True, choices=ShippingMethod.choices
    )

    product_type = models.IntegerField(
        null=False, blank=False, choices=ProductType.choices, default=ProductType.T_SHIRT
    )
    fit = models.IntegerField(null=False, blank=False, choices=Fit.choices)
    size = models.IntegerField(null=False, blank=False, choices=Size.choices)
    print_color = models.IntegerField(null=False, blank=False, choices=PrintColor.choices)

    def shipping_name(self):
        if self.shipping_details:
            return self.shipping_details.get("name")
        return None

    def shipping_line1(self):
        if self.shipping_details:
            return self.shipping_details.get("address", {}).get("line1")
        return None

    def shipping_line2(self):
        if self.shipping_details:
            return self.shipping_details.get("address", {}).get("line2")
        return None

    def shipping_city(self):
        if self.shipping_details:
            return self.shipping_details.get("address", {}).get("city")
        return None

    def shipping_state(self):
        if self.shipping_details:
            return self.shipping_details.get("address", {}).get("state")
        return None

    def shipping_postal_code(self):
        if self.shipping_details:
            return self.shipping_details.get("address", {}).get("postal_code")
        return None
