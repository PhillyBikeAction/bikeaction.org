import uuid

from django.contrib.auth.models import User
from django.db import models, transaction
from djstripe.models import Price, Product
from markdownfield.models import RenderedMarkdownField
from ordered_model.models import OrderedModel

from membership.tasks import (
    sync_donation_product_to_stripe,
    sync_donation_tier_to_stripe,
)
from pbaabp.models import MarkdownField


class DonationProduct(OrderedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stripe_product = models.ForeignKey(Product, blank=True, null=True, on_delete=models.SET_NULL)

    active = models.BooleanField(blank=False, default=False)

    name = models.CharField(max_length=512)
    description = models.TextField(null=True, blank=True)
    disclaimer = MarkdownField(rendered_field="disclaimer_rendered", null=True, blank=True)
    disclaimer_rendered = RenderedMarkdownField()

    def save(self, *args, **kwargs):
        if self._state.adding:
            transaction.on_commit(lambda: sync_donation_product_to_stripe.delay(self.id))
        else:
            old_model = DonationProduct.objects.get(pk=self.pk)
            change_fields = [
                f.name
                for f in DonationProduct._meta._get_fields()
                if f.name not in ["id", "stripe_product"]
            ]
            modified = False
            for i in change_fields:
                if getattr(old_model, i, None) != getattr(self, i, None):
                    modified = True
            if modified:
                transaction.on_commit(lambda: sync_donation_product_to_stripe.delay(self.id))
        super(DonationProduct, self).save(*args, **kwargs)

    def __str__(self):
        return f"Donation: {self.name}"


class Donation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    donation_product = models.ForeignKey(
        DonationProduct, blank=True, null=True, on_delete=models.SET_NULL, related_name="donations"
    )
    comment = models.CharField(max_length=256, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False)

    def __str__(self):
        if self.comment and not self.donation_product:
            return f'Donation of ${self.amount} - "{self.comment}"'
        if self.comment and self.donation_product:
            return '"Donation of ${self.amount} to {self.donation_product.name} - "{self.comment}"'
        return f"Donation of ${self.amount} to {self.donation_product.name}"


class DonationTier(OrderedModel):
    class Recurrence(models.IntegerChoices):
        MONTHLY = 0, "month"
        ANNUAL = 1, "year"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stripe_price = models.ForeignKey(Price, blank=True, null=True, on_delete=models.SET_NULL)

    active = models.BooleanField(blank=False, default=False)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False)
    recurrence = models.IntegerField(null=False, blank=False, choices=Recurrence.choices)

    def save(self, *args, **kwargs):
        if self._state.adding:
            transaction.on_commit(lambda: sync_donation_tier_to_stripe.delay(self.id))
        else:
            old_model = DonationTier.objects.get(pk=self.pk)
            change_fields = [
                f.name
                for f in DonationTier._meta._get_fields()
                if f.name not in ["id", "stripe_price"]
            ]
            modified = False
            for i in change_fields:
                if getattr(old_model, i, None) != getattr(self, i, None):
                    modified = True
            if modified:
                transaction.on_commit(lambda: sync_donation_tier_to_stripe.delay(self.id))
        super(DonationTier, self).save(*args, **kwargs)

    def __str__(self):
        return f"${self.cost}/{self.get_recurrence_display()}"


class Membership(models.Model):
    class Kind(models.IntegerChoices):
        FISCAL = 0, "Fiscal"
        PARTICIPATION = 1, "Participation"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    kind = models.IntegerField(null=False, blank=False, choices=Kind.choices)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        end_str = f" to {self.end_date}" if self.end_date else " (ongoing)"
        return f"{self.user.email} - {self.get_kind_display()} - {self.start_date}{end_str}"
