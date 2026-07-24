import datetime

from django.contrib.auth.models import User
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from email_log.models import Email

from facets.models import District, RegisteredCommunityOrganization
from facets.views import _email_report_time_window
from profiles.models import Profile


class EmailReportTimeWindowTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime.datetime(2026, 7, 23, 12, 0, tzinfo=datetime.UTC)

    def test_email_report_defaults_to_30_days(self):
        window = _email_report_time_window(None, now=self.now)

        self.assertEqual(window["selected"], "30")
        self.assertEqual(window["start_at"], self.now - datetime.timedelta(days=30))
        self.assertEqual(window["date_range"], "Last 30 days (since 2026-06-23)")

    def test_email_report_supports_90_day_window(self):
        window = _email_report_time_window("90", now=self.now)

        self.assertEqual(window["selected"], "90")
        self.assertEqual(window["start_at"], self.now - datetime.timedelta(days=90))
        self.assertEqual(window["date_range"], "Last 90 days (since 2026-04-24)")

    def test_email_report_supports_one_year_window(self):
        window = _email_report_time_window("365", now=self.now)

        self.assertEqual(window["selected"], "365")
        self.assertEqual(window["start_at"], self.now - datetime.timedelta(days=365))
        self.assertEqual(window["date_range"], "Last 1 year (since 2025-07-23)")

    def test_email_report_supports_all_time_window(self):
        window = _email_report_time_window("all", now=self.now)

        self.assertEqual(window["selected"], "all")
        self.assertIsNone(window["start_at"])
        self.assertEqual(window["date_range"], "All time")

    def test_email_report_invalid_window_falls_back_to_default(self):
        window = _email_report_time_window("not-a-window", now=self.now)

        self.assertEqual(window["selected"], "30")
        self.assertEqual(window["start_at"], self.now - datetime.timedelta(days=30))

    def test_email_report_marks_selected_option(self):
        window = _email_report_time_window("90", now=self.now)

        self.assertEqual(
            window["options"],
            [
                {"value": "30", "label": "30 days", "selected": False},
                {"value": "90", "label": "90 days", "selected": True},
                {"value": "365", "label": "1 year", "selected": False},
                {"value": "all", "label": "All time", "selected": False},
            ],
        )


class EmailReportViewTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="password",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def create_facet(self, model, name):
        polygon = Polygon(
            (
                (0, 0),
                (2, 0),
                (2, 2),
                (0, 2),
                (0, 0),
            ),
            srid=4326,
        )
        return model.objects.create(
            name=name,
            mpoly=MultiPolygon(polygon, srid=4326),
            properties={},
            targetable=True,
        )

    def create_profile(self):
        user = User.objects.create_user(username="rider", email="rider@example.com")
        return Profile.objects.create(user=user, location=Point(1, 1, srid=4326))

    def create_email(self, *, date_sent):
        email = Email.objects.create(
            from_email="organizer@example.com",
            recipients="Rider <rider@example.com>",
            subject="Project update",
            body="Message",
            date_sent=date_sent,
        )
        Email.objects.filter(pk=email.pk).update(date_sent=date_sent)
        email.refresh_from_db()
        return email

    def test_selected_time_window_updates_district_and_rco_email_totals(self):
        self.create_facet(District, "District 1")
        self.create_facet(RegisteredCommunityOrganization, "RCO 1")
        self.create_profile()
        self.create_email(date_sent=timezone.now() - datetime.timedelta(days=20))
        self.create_email(date_sent=timezone.now() - datetime.timedelta(days=60))

        default_response = self.client.get(reverse("rco_email_report"))
        ninety_day_response = self.client.get(
            reverse("rco_email_report"),
            {"time_window": "90"},
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(ninety_day_response.status_code, 200)
        self.assertEqual(default_response.context["districts"][0]["total_emails"], 1)
        self.assertEqual(default_response.context["rcos"][0]["total_emails"], 1)
        self.assertEqual(ninety_day_response.context["districts"][0]["total_emails"], 2)
        self.assertEqual(ninety_day_response.context["rcos"][0]["total_emails"], 2)
