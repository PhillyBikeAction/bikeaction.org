import datetime

from django.test import SimpleTestCase

from facets.views import _email_report_time_window


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
