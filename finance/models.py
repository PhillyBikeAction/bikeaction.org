import uuid
from pathlib import Path

from django.db import models
from django.utils.text import slugify


def reimbursement_expense_support_upload_to(instance, filename):
    original_file = Path(filename)
    return (
        "reimbursement-expense-support/"
        f"{slugify(instance.vendor_name)}-{slugify(original_file.stem)}-"
        f"{uuid.uuid4().hex[:8]}{original_file.suffix.lower()}"
    )

class Reimbursement(models.Model):
    class ReimbursementMethod(models.TextChoices):
        ZELLE = "zelle", "Zelle"
        PAYPAL = "paypal", "PayPal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    first_name = models.CharField(max_length=64, null=False, blank=False)
    last_name = models.CharField(max_length=64, null=False, blank=False)
    email = models.EmailField(max_length=100, null=False, blank=False)
    discord_handle = models.CharField(max_length=64, null=True, blank=True)

    vendor_name = models.CharField(max_length=256, null=False, blank=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False)
    expense_date = models.DateField(null=False, blank=False)
    explanation = models.TextField(max_length=250, null=False, blank=False)
    expense_support = models.FileField(upload_to=reimbursement_expense_support_upload_to)

    reimbursement_method = models.CharField(
        max_length=16, choices=ReimbursementMethod.choices, null=False, blank=False
    )
    payment_contact = models.CharField(max_length=256, null=False, blank=False)

    def __str__(self):
        return (
            f"{self.first_name} {self.last_name} - "
            f"{self.vendor_name} - ${self.amount} - "
            f"{self.expense_date.strftime('%Y-%m-%d')}"
        )
