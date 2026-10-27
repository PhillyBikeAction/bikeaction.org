import shutil
import tempfile
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from finance.forms import MAX_EXPENSE_SUPPORT_FILES, ReimbursementForm
from finance.models import (
    Reimbursement,
    ReimbursementSupportingMaterial,
    reimbursement_expense_support_upload_to,
)



class ReimbursementFormTests(SimpleTestCase):
    test_reimbursement = Reimbursement(
        first_name = "Taylor",
        last_name = "Requester",
        email = "taylor@example.com",
        discord_handle = "",
        reimbursement_method = "zelle",
        payment_contact = "taylor@example.com",
        vendor_name = "Bike Shop",
        amount = "42.50",
        expense_date = "2026-10-01",
        explanation = "Food"
    )
    
    def test_supporting_material_filename_is_unique_with_lowercase_extension(self):
        material = ReimbursementSupportingMaterial(application=self.test_reimbursement)

        filename = reimbursement_expense_support_upload_to(material, "Site Plan.PDF")

        self.assertTrue(
            filename.startswith("reimbursement-expense-support/")
        )
        self.assertTrue(filename.endswith(".pdf"))
        self.assertNotEqual(
            filename,
            reimbursement_expense_support_upload_to(material, "Site Plan.PDF"),
        )

    def test_accepts_multiple_supporting_materials(self):
        files = [
            SimpleUploadedFile("sketch.pdf", b"sketch"),
            SimpleUploadedFile("budget.xlsx", b"budget"),
        ]
        form = ReimbursementForm()
        form.cleaned_data = {"expense_support": files}

        self.assertEqual(form.clean_expense_support(), files)

    def test_too_many_files(self):
        files = [
            SimpleUploadedFile("sketch.pdf", b"sketch"),
            SimpleUploadedFile("budget.xlsx", b"budget"),
            SimpleUploadedFile("sketch1.pdf", b"sketch"),
            SimpleUploadedFile("budget12.xlsx", b"budget"),
            SimpleUploadedFile("sketch12.pdf", b"sketch"),
            SimpleUploadedFile("budget123.xlsx", b"budget"),
        ]
        form = ReimbursementForm()
        form.cleaned_data = {"expense_support": files}

        with self.assertRaisesMessage(
            ValidationError,
            f"Please upload no more than {MAX_EXPENSE_SUPPORT_FILES} files.",
        ):
            form.clean_expense_support()
    def test_attachment_required(self):
        files = [
        ]
        form = ReimbursementForm()
        form.cleaned_data = {"expense_support": files}

        with self.assertRaisesMessage(
            ValidationError,
            "Please attach at least one file.",
        ):
            form.clean_expense_support()

    def test_requires_explanation(self):
        data={
             "first_name": "Taylor",
            "last_name": "Requester",
            "email":"taylor@example.com",
            "discord_handle": "",
            "reimbursement_method": "zelle",
            "payment_contact": "taylor@example.com",
            "vendor_name": "Bike Shop",
            "amount": "42.50",
            "expense_date": "2026-10-01",
        }
        form = ReimbursementForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("explanation", form.errors)
    
    def test_amount_requested_must_be_positive(self):
        field = ReimbursementForm.base_fields["amount"]

        self.assertEqual(field.clean("0.01"), Decimal("0.01"))
        with self.assertRaises(ValidationError):
            field.clean("0")

    def test_rejects_explanation_over_character_limit(self):
        form = ReimbursementForm(
            data={
                "first_name": "Taylor",
                "last_name": "Requester",
                "email":"taylor@example.com",
                "discord_handle": "",
                "reimbursement_method": "zelle",
                "payment_contact": "taylor@example.com",
                "vendor_name": "Bike Shop",
                "amount": "42.50",
                "expense_date": "2026-10-01",
                "explanation": "word " * 301,
            }

        )
        self.assertFalse(form.is_valid())
        self.assertIn("explanation", form.errors)

    def test_rejects_vendor_over_character_limit(self):
        form = ReimbursementForm(
            data={
                "first_name": "Taylor",
                "last_name": "Requester",
                "email":"taylor@example.com",
                "discord_handle": "",
                "reimbursement_method": "zelle",
                "payment_contact": "taylor@example.com",
                "vendor_name": "B" * 300,
                "amount": "42.50",
                "expense_date": "2026-10-01",
            }

        )
        self.assertFalse(form.is_valid())
        self.assertIn("vendor_name", form.errors)


    def test_reimbursement_decision_choices(self):
        self.assertEqual(Reimbursement.Decision.APPROVED, "approved")
        self.assertEqual(Reimbursement.Decision.PENDING, "pending")
        self.assertEqual(Reimbursement.Decision.DENIED, "denied")

    def test_rejects_unknown_reimbursement_method(self):
        data={
            "first_name": "Taylor",
            "last_name": "Requester",
            "email":"taylor@example.com",
            "discord_handle": "",
            "reimbursement_method": "ali pay",
            "payment_contact": "taylor@example.com",
            "vendor_name": "Bike Shop",
            "amount": "42.50",
            "expense_date": "2026-10-01",
            "explanation": "Food",
        }
        form = ReimbursementForm(
            data
        )

        self.assertFalse(form.is_valid())
        self.assertIn("reimbursement_method", form.errors)

# TODO: Should I have a test here checking if user is logged in?
