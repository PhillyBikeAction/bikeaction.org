from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from community_fund.forms import CommunityActionFundApplicationForm
from community_fund.models import (
    CommunityActionFundApplication,
    CommunityActionFundApplicationPeriod,
    CommunityActionFundSupportingMaterial,
    community_action_fund_supporting_material_upload_to,
)
from community_fund.tasks import DISCORD_MESSAGE_LIMIT, split_discord_messages


class CommunityActionFundApplicationFormTests(SimpleTestCase):
    def test_splits_an_unbroken_discord_line(self):
        markdown = "x" * (DISCORD_MESSAGE_LIMIT + 1)

        messages = split_discord_messages(markdown)

        self.assertEqual("".join(messages).strip(), markdown)
        self.assertTrue(all(len(message) <= DISCORD_MESSAGE_LIMIT for message in messages))

    def test_supporting_material_filename_uses_project_title(self):
        application = CommunityActionFundApplication(
            data={"project_title": {"value": "Safer Bike Routes"}}
        )
        material = CommunityActionFundSupportingMaterial(application=application)

        filename = community_action_fund_supporting_material_upload_to(material, "Site Plan.PDF")

        self.assertTrue(
            filename.startswith("community-fund-supporting-materials/safer-bike-routes-site-plan-")
        )
        self.assertTrue(filename.endswith(".pdf"))
        self.assertNotEqual(
            filename,
            community_action_fund_supporting_material_upload_to(material, "Site Plan.PDF"),
        )

    def test_accepts_multiple_supporting_materials(self):
        files = [
            SimpleUploadedFile("sketch.pdf", b"sketch"),
            SimpleUploadedFile("budget.xlsx", b"budget"),
        ]
        form = CommunityActionFundApplicationForm(files={"supporting_materials": files})

        self.assertEqual(form.fields["supporting_materials"].clean(files), files)

    def test_requires_explanation_for_upfront_funding(self):
        form = CommunityActionFundApplicationForm(
            data={
                "primary_contact_name": "Taylor Applicant",
                "email": "taylor@example.com",
                "phone": "215-555-0123",
                "project_title": "Safer bike route",
                "project_description": "A safer bike route.",
                "community_impact": "People who bike will benefit.",
                "project_readiness": "We will obtain permission and install it.",
                "amount_requested": "500",
                "estimated_total_project_cost": "600",
                "funding_preference": "upfront",
                "certification": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("funding_preference_explanation", form.errors)

    def test_amount_requested_must_be_positive(self):
        field = CommunityActionFundApplicationForm.base_fields["amount_requested"]

        self.assertEqual(field.clean("0.01"), Decimal("0.01"))
        with self.assertRaises(ValidationError):
            field.clean("0")

    def test_rejects_responses_over_word_limit(self):
        form = CommunityActionFundApplicationForm(
            data={
                "primary_contact_name": "Taylor Applicant",
                "email": "taylor@example.com",
                "phone": "215-555-0123",
                "project_title": "Safer bike route",
                "project_description": "word " * 301,
                "community_impact": "People who bike will benefit.",
                "project_readiness": "We will obtain permission and install it.",
                "amount_requested": "500",
                "estimated_total_project_cost": "600",
                "funding_preference": "reimbursement",
                "certification": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("project_description", form.errors)

    def test_application_decision_choices(self):
        self.assertEqual(CommunityActionFundApplication.Decision.APPROVED, "approved")
        self.assertEqual(CommunityActionFundApplication.Decision.DECLINED, "declined")

    def test_application_period_string(self):
        now = timezone.now()
        period = CommunityActionFundApplicationPeriod(
            name="Fall 2026", starts_at=now, ends_at=now + timedelta(days=1)
        )

        self.assertIn("Fall 2026", str(period))


class CommunityActionFundApplicationPeriodTests(TestCase):
    def test_applications_are_open_only_during_an_active_period(self):
        now = timezone.now()
        self.assertFalse(CommunityActionFundApplicationPeriod.applications_are_open())

        CommunityActionFundApplicationPeriod.objects.create(
            name="Current round",
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )

        self.assertTrue(CommunityActionFundApplicationPeriod.applications_are_open())
