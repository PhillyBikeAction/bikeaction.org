import json
import shutil
import tempfile
from unittest.mock import Mock, patch

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from campaigns.models import Petition, PetitionSignature
from emailblasts.admin import send_selected_email_blasts
from emailblasts.forms import EmailDraftForm
from emailblasts.models import (
    EmailBlast,
    EmailBlastDelivery,
    EmailBlastImage,
    EmailBlastTarget,
    EmailBlastTargetNode,
)
from emailblasts.tasks import send_email_blast
from emailblasts.targeting import _email_blast_target_profiles
from emailblasts.views import (
    _email_blast_target_object,
    _email_draft_geojson_feature_collection,
    _email_draft_profiles_for_targets,
    _email_draft_target_name,
)
from events.models import EventSignIn, ScheduledEvent
from facets.models import District, ZipCode
from pbaabp.email import render_email_html, send_email_message
from profiles.models import DoNotEmail, Profile


class EmailBlastSendTaskTests(TestCase):
    def create_profile(self, email, first_name="Test", last_name="User"):
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        return Profile.objects.create(user=user)

    def create_all_profiles_blast(self, subject="Test blast"):
        target = EmailBlastTarget.objects.create(
            name="All profiles",
            description="have a PBA account",
        )
        root = EmailBlastTargetNode.objects.create(
            target=target,
            operator=EmailBlastTargetNode.Operator.OR,
        )
        EmailBlastTargetNode.objects.create(
            target=target,
            parent=root,
            primitive_type=EmailBlastTargetNode.TargetType.ALL_PROFILES,
            primitive_name=EmailBlastTargetNode.TargetType.ALL_PROFILES.label,
        )
        return EmailBlast.objects.create(
            subject=subject,
            body="Main message",
            reply_to="organizer@bikeaction.org",
            target=target,
            status=EmailBlast.Status.APPROVED,
        )

    @patch("emailblasts.tasks.send_email_message")
    def test_second_queued_task_does_not_send_duplicate_blast(self, mock_send_email):
        self.create_profile("one@example.com", first_name="One")
        self.create_profile("two@example.com", first_name="Two")
        blast = self.create_all_profiles_blast()

        send_email_blast(blast.id)
        send_email_blast(blast.id)

        self.assertEqual(mock_send_email.call_count, 2)
        self.assertEqual(EmailBlastDelivery.objects.filter(email_blast=blast).count(), 2)
        blast.refresh_from_db()
        self.assertEqual(blast.status, EmailBlast.Status.SENT)

    @patch("emailblasts.tasks.send_email_message")
    def test_suppressed_recipient_is_skipped_case_insensitively(self, mock_send_email):
        self.create_profile("CaseSensitive@example.com")
        DoNotEmail.objects.create(
            email="casesensitive@example.com",
            reason=DoNotEmail.Reason.ACCOUNT_DELETION,
        )
        blast = self.create_all_profiles_blast()

        result = send_email_blast(blast.id)

        mock_send_email.assert_not_called()
        self.assertEqual(EmailBlastDelivery.objects.filter(email_blast=blast).count(), 0)
        self.assertIn("skipped 1 suppressed recipients", result)
        blast.refresh_from_db()
        self.assertEqual(blast.status, EmailBlast.Status.SENT)

    @patch("emailblasts.tasks.send_email_message")
    def test_failed_recipient_send_can_be_retried(self, mock_send_email):
        self.create_profile("retry@example.com")
        blast = self.create_all_profiles_blast()
        mock_send_email.side_effect = [RuntimeError("smtp down"), None]

        with self.assertRaises(RuntimeError):
            send_email_blast(blast.id)

        blast.refresh_from_db()
        self.assertEqual(blast.status, EmailBlast.Status.APPROVED)
        self.assertEqual(EmailBlastDelivery.objects.filter(email_blast=blast).count(), 0)

        send_email_blast(blast.id)

        self.assertEqual(mock_send_email.call_count, 2)
        self.assertEqual(EmailBlastDelivery.objects.filter(email_blast=blast).count(), 1)
        blast.refresh_from_db()
        self.assertEqual(blast.status, EmailBlast.Status.SENT)

    @patch("emailblasts.tasks.send_email_message")
    def test_retry_does_not_email_existing_successful_delivery(self, mock_send_email):
        first_profile = self.create_profile("already@example.com", first_name="Already")
        self.create_profile("new@example.com", first_name="New")
        blast = self.create_all_profiles_blast()
        EmailBlastDelivery.objects.create(
            email_blast=blast,
            profile=first_profile,
            email="already@example.com",
            sent_at=timezone.now(),
        )

        send_email_blast(blast.id)

        self.assertEqual(mock_send_email.call_count, 1)
        self.assertEqual(mock_send_email.call_args.kwargs["to"], ["new@example.com"])
        self.assertEqual(EmailBlastDelivery.objects.filter(email_blast=blast).count(), 2)
        blast.refresh_from_db()
        self.assertEqual(blast.status, EmailBlast.Status.SENT)

    @patch("emailblasts.tasks.send_email_message")
    def test_retry_sends_existing_unsent_delivery(self, mock_send_email):
        profile = self.create_profile("reserved@example.com", first_name="Reserved")
        blast = self.create_all_profiles_blast()
        EmailBlastDelivery.objects.create(
            email_blast=blast,
            profile=profile,
            email="reserved@example.com",
            sent_at=None,
        )

        send_email_blast(blast.id)

        mock_send_email.assert_called_once()
        delivery = EmailBlastDelivery.objects.get(email_blast=blast, email="reserved@example.com")
        self.assertIsNotNone(delivery.sent_at)
        blast.refresh_from_db()
        self.assertEqual(blast.status, EmailBlast.Status.SENT)


class EmailBlastAdminActionTests(TestCase):
    def create_blast(self, subject, status):
        return EmailBlast.objects.create(
            subject=subject,
            body="Main message",
            reply_to="organizer@bikeaction.org",
            status=status,
        )

    @patch("emailblasts.admin.send_email_blast.delay")
    def test_send_selected_email_blasts_queues_approved_blasts(self, mock_delay):
        blast = self.create_blast("Approved blast", EmailBlast.Status.APPROVED)
        modeladmin = Mock()
        request = Mock()

        with self.captureOnCommitCallbacks(execute=True):
            send_selected_email_blasts(
                modeladmin,
                request,
                EmailBlast.objects.filter(id=blast.id),
            )

        mock_delay.assert_called_once_with(blast.id)
        modeladmin.message_user.assert_called_once_with(
            request,
            "1 email blast queued to send.",
        )

    @patch("emailblasts.admin.send_email_blast.delay")
    def test_send_selected_email_blasts_blocks_unapproved_blasts(self, mock_delay):
        approved_blast = self.create_blast("Approved blast", EmailBlast.Status.APPROVED)
        submitted_blast = self.create_blast("Submitted blast", EmailBlast.Status.SUBMITTED)
        modeladmin = Mock()
        request = Mock()

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            send_selected_email_blasts(
                modeladmin,
                request,
                EmailBlast.objects.filter(id__in=[approved_blast.id, submitted_blast.id]),
            )

        self.assertEqual(callbacks, [])
        mock_delay.assert_not_called()
        modeladmin.message_user.assert_called_once_with(
            request,
            "1 email blast not queued; this action can only be used when all selected "
            "blasts are approved.",
            level=messages.ERROR,
        )


class EmailBlastImageTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_root,
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        )
        self.settings_override.enable()
        self.user = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="password",
        )
        permission = Permission.objects.get(codename="can_organize")
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root)

    def test_image_upload_returns_markdown_for_email_body(self):
        image = SimpleUploadedFile(
            "banner.png",
            b"not-really-a-png",
            content_type="image/png",
        )

        response = self.client.post(reverse("email_draft_upload_image"), {"image": image})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["markdown"].startswith("![banner.png](media/emailblasts/images/"))
        self.assertEqual(EmailBlastImage.objects.count(), 1)
        uploaded = EmailBlastImage.objects.get()
        self.assertEqual(uploaded.created_by, self.user)
        self.assertTrue(uploaded.image.storage.exists(uploaded.image.name))

    def test_preview_rewrites_uploaded_media_image_paths(self):
        html = render_email_html(
            "![Banner](media/emailblasts/images/banner.png)",
            for_preview=True,
        )

        self.assertIn("/media/emailblasts/images/banner.png", html)

    @patch("pbaabp.email.default_storage.url")
    def test_preview_uses_storage_url_for_uploaded_media_image_paths(self, mock_storage_url):
        mock_storage_url.return_value = "https://media.example.com/emailblasts/images/banner.png"

        html = render_email_html(
            "![Banner](media/emailblasts/images/banner.png)",
            for_preview=True,
        )

        mock_storage_url.assert_called_once_with("emailblasts/images/banner.png")
        self.assertIn("https://media.example.com/emailblasts/images/banner.png", html)

    def test_send_email_inlines_uploaded_media_image_from_storage(self):
        image = SimpleUploadedFile(
            "banner.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00"
            b"\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        email_image = EmailBlastImage.objects.create(
            created_by=self.user,
            image=image,
            original_filename="banner.gif",
        )

        send_email_message(
            template_name=None,
            from_=None,
            to=["organizer@example.com"],
            context={},
            subject="Image test",
            message=f"![Banner]({email_image.email_src})",
        )

        self.assertEqual(len(mail.outbox), 1)

    def test_send_email_inlines_uploaded_media_image_with_media_url_path(self):
        image = SimpleUploadedFile(
            "banner.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00"
            b"\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        email_image = EmailBlastImage.objects.create(
            created_by=self.user,
            image=image,
            original_filename="banner.gif",
        )

        send_email_message(
            template_name=None,
            from_=None,
            to=["organizer@example.com"],
            context={},
            subject="Image test",
            message=f"![Banner](/media/{email_image.image.name})",
        )

        self.assertEqual(len(mail.outbox), 1)

    @patch("pbaabp.email.default_storage.url")
    def test_send_email_inlines_uploaded_media_image_with_storage_url(self, mock_storage_url):
        mock_storage_url.return_value = "https://media.example.com/"
        image = SimpleUploadedFile(
            "banner.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00"
            b"\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        email_image = EmailBlastImage.objects.create(
            created_by=self.user,
            image=image,
            original_filename="banner.gif",
        )

        send_email_message(
            template_name=None,
            from_=None,
            to=["organizer@example.com"],
            context={},
            subject="Image test",
            message=f"![Banner](https://media.example.com/{email_image.image.name})",
        )

        self.assertEqual(len(mail.outbox), 1)

    def test_send_email_leaves_external_https_images_remote(self):
        send_email_message(
            template_name=None,
            from_=None,
            to=["organizer@example.com"],
            context={},
            subject="External image test",
            message="![Remote](https://example.com/banner.png)",
        )

        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("https://example.com/banner.png", html)


class EmailBlastExampleSendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="password",
            first_name="Olivia",
            last_name="Organizer",
        )
        permission = Permission.objects.get(codename="can_organize")
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

    def form_data(self, **overrides):
        data = {
            "subject": "Test blast",
            "reply_to": "reply@bikeaction.org",
            "target_name": "All profiles",
            "target_description": "have a PBA account",
            "target_operator": EmailBlastTargetNode.Operator.OR,
            "body": "Main message",
            "target_type_0": EmailBlastTargetNode.TargetType.ALL_PROFILES,
            "target_value_0": "",
            "target_geojson_0": "",
            "action": "send_example",
        }
        data.update(overrides)
        return data

    @patch("emailblasts.views.send_email_message")
    def test_send_example_emails_current_user_without_saving_blast(self, mock_send_email):
        response = self.client.post(reverse("email_draft"), self.form_data())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(EmailBlast.objects.count(), 0)
        mock_send_email.assert_called_once()
        self.assertEqual(mock_send_email.call_args.kwargs["to"], ["organizer@example.com"])
        self.assertEqual(mock_send_email.call_args.kwargs["subject"], "[TEST] Test blast")
        self.assertEqual(mock_send_email.call_args.kwargs["reply_to"], ["reply@bikeaction.org"])
        self.assertIn("Hi {{ first_name }}", mock_send_email.call_args.kwargs["message"])


class EmailBlastTargetingTests(TestCase):
    def create_profile(self, email, longitude, latitude):
        user = User.objects.create_user(username=email, email=email)
        return Profile.objects.create(user=user, location=Point(longitude, latitude, srid=4326))

    def create_district(self, name, min_x, min_y, max_x, max_y):
        return self.create_facet(District, name, min_x, min_y, max_x, max_y)

    def create_zip_code(self, name, min_x, min_y, max_x, max_y):
        return self.create_facet(ZipCode, name, min_x, min_y, max_x, max_y)

    def create_facet(self, model, name, min_x, min_y, max_x, max_y):
        polygon = Polygon(
            (
                (min_x, min_y),
                (max_x, min_y),
                (max_x, max_y),
                (min_x, max_y),
                (min_x, min_y),
            ),
            srid=4326,
        )
        return model.objects.create(
            name=name,
            mpoly=MultiPolygon(polygon, srid=4326),
            properties={},
        )

    def target_data(self, target_type, target_id, target_name):
        return {
            "target_type": target_type,
            "target_id": str(target_id),
            "target_name": target_name,
            "target_geojson": None,
        }

    def create_event(self, title="Test Event"):
        return ScheduledEvent.objects.create(
            title=title,
            status=ScheduledEvent.Status.SCHEDULED,
            start_datetime=timezone.now(),
        )

    def form_data(self, **overrides):
        data = {
            "subject": "Test blast",
            "reply_to": "organizer@bikeaction.org",
            "target_name": "All profiles",
            "target_description": "have a PBA account",
            "target_operator": EmailBlastTargetNode.Operator.OR,
            "body": "Main message",
            "target_type_0": EmailBlastTargetNode.TargetType.ALL_PROFILES,
            "target_value_0": "",
            "target_geojson_0": "",
        }
        data.update(overrides)
        return data

    def test_invalid_template_syntax_is_rejected_by_form(self):
        form = EmailDraftForm(data=self.form_data(body="Hello {% if first_name %}"))

        self.assertFalse(form.is_valid())
        self.assertIn("template syntax", str(form.errors["__all__"]))

    def test_invalid_template_syntax_in_recipient_reason_is_rejected_by_form(self):
        form = EmailDraftForm(
            data=self.form_data(target_description="live nearby {% if first_name %}")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("template syntax", str(form.errors["__all__"]))

    def test_district_targets_can_be_combined_with_or_and_and(self):
        west = self.create_profile("west@example.com", 0.5, 0.5)
        middle = self.create_profile("middle@example.com", 1.5, 1.5)
        east = self.create_profile("east@example.com", 2.5, 2.5)
        district_1 = self.create_district("District 1", 0, 0, 2, 2)
        district_2 = self.create_district("District 2", 1, 1, 3, 3)
        targets = [
            self.target_data(
                EmailBlastTargetNode.TargetType.DISTRICT,
                district_1.pk,
                str(district_1),
            ),
            self.target_data(
                EmailBlastTargetNode.TargetType.DISTRICT,
                district_2.pk,
                str(district_2),
            ),
        ]

        or_profiles = _email_draft_profiles_for_targets(
            targets,
            EmailBlastTargetNode.Operator.OR,
        )
        and_profiles = _email_draft_profiles_for_targets(
            targets,
            EmailBlastTargetNode.Operator.AND,
        )

        self.assertCountEqual(or_profiles, [west, middle, east])
        self.assertCountEqual(and_profiles, [middle])
        self.assertEqual(
            _email_draft_target_name(targets, EmailBlastTargetNode.Operator.AND),
            "District 1 AND District 2",
        )

    def test_all_profiles_target_overrides_other_targets(self):
        first = self.create_profile("first@example.com", 0.5, 0.5)
        second = self.create_profile("second@example.com", 10, 10)
        district = self.create_district("District 1", 0, 0, 2, 2)
        targets = [
            self.target_data(
                EmailBlastTargetNode.TargetType.DISTRICT,
                district.pk,
                str(district),
            ),
            self.target_data(
                EmailBlastTargetNode.TargetType.ALL_PROFILES,
                "",
                EmailBlastTargetNode.TargetType.ALL_PROFILES.label,
            ),
        ]

        profiles = _email_draft_profiles_for_targets(targets)

        self.assertCountEqual(profiles, [first, second])

    def test_zip_code_target_matches_profiles_inside_zip_code_facet(self):
        inside = self.create_profile("inside@example.com", 0.5, 0.5)
        self.create_profile("outside@example.com", 2.5, 2.5)
        zip_code = self.create_zip_code("19125", 0, 0, 2, 2)
        target = self.target_data(
            EmailBlastTargetNode.TargetType.ZIP_CODE,
            zip_code.pk,
            str(zip_code),
        )

        profiles = _email_draft_profiles_for_targets([target])

        self.assertCountEqual(profiles, [inside])

    def test_petition_target_matches_profiles_by_signer_email(self):
        signer = self.create_profile("signer@example.com", 0, 0)
        self.create_profile("other@example.com", 0, 0)
        petition = Petition.objects.create(title="Safer Streets")
        PetitionSignature.objects.create(
            petition=petition,
            first_name="Signer",
            email="signer@example.com",
        )
        target = self.target_data(
            EmailBlastTargetNode.TargetType.PETITION,
            petition.pk,
            str(petition),
        )

        profiles = _email_draft_profiles_for_targets([target])

        self.assertCountEqual(profiles, [signer])

    def test_petition_target_matches_profiles_by_signer_email_case_insensitively(self):
        signer = self.create_profile("Signer@Example.com", 0, 0)
        petition = Petition.objects.create(title="Safer Streets")
        PetitionSignature.objects.create(
            petition=petition,
            first_name="Signer",
            email="signer@example.com",
        )
        target = self.target_data(
            EmailBlastTargetNode.TargetType.PETITION,
            petition.pk,
            str(petition),
        )

        profiles = _email_draft_profiles_for_targets([target])

        self.assertCountEqual(profiles, [signer])

    def test_event_signin_target_matches_profiles_by_signin_email_case_insensitively(self):
        attendee = self.create_profile("Attendee@Example.com", 0, 0)
        self.create_profile("other@example.com", 0, 0)
        event = self.create_event("May Meetup")
        EventSignIn.objects.create(
            event=event,
            first_name="Attendee",
            last_name="Person",
            email="attendee@example.com",
            council_district=EventSignIn.District.DISTRICT_1,
        )
        target = self.target_data(
            EmailBlastTargetNode.TargetType.EVENT_SIGNIN,
            event.pk,
            str(event),
        )

        profiles = _email_draft_profiles_for_targets([target])

        self.assertCountEqual(profiles, [attendee])

    def test_persisted_target_evaluates_same_composed_logic(self):
        user = User.objects.create_user(username="organizer", email="organizer@example.com")
        self.create_profile("west@example.com", 0.5, 0.5)
        middle = self.create_profile("middle@example.com", 1.5, 1.5)
        self.create_profile("east@example.com", 2.5, 2.5)
        district_1 = self.create_district("District 1", 0, 0, 2, 2)
        district_2 = self.create_district("District 2", 1, 1, 3, 3)
        targets = [
            self.target_data(
                EmailBlastTargetNode.TargetType.DISTRICT,
                district_1.pk,
                str(district_1),
            ),
            self.target_data(
                EmailBlastTargetNode.TargetType.DISTRICT,
                district_2.pk,
                str(district_2),
            ),
        ]
        persisted_target = _email_blast_target_object(
            "Intersection target",
            "live in both districts",
            EmailBlastTargetNode.Operator.AND,
            targets,
            user,
        )

        profiles = _email_blast_target_profiles(persisted_target)

        self.assertCountEqual(profiles, [middle])

    def test_geojson_feature_collection_linestring_is_accepted_and_rendered_as_polygon(self):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [-75.21064675141389, 39.952362055357696],
                            [-75.20922893702708, 39.952151222621524],
                            [-75.20944056749815, 39.951348204967275],
                        ],
                    },
                }
            ],
        }
        form = EmailDraftForm()

        cleaned_geojson = form.clean_geojson_boundary(value=json.dumps(geojson))
        feature_collection = _email_draft_geojson_feature_collection(
            [
                {
                    "target_type": EmailBlastTargetNode.TargetType.GEOJSON,
                    "target_id": "",
                    "target_name": "GeoJSON boundary",
                    "target_geojson": cleaned_geojson,
                }
            ]
        )

        self.assertIn('"type": "MultiPolygon"', feature_collection)
