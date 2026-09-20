from django.conf import settings
from django.test import TestCase
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.models import Locale, Page, Site

from cms.models import CmsStreamPage, HomePage, NavigationContainerPage


class BreadcrumbsTests(TestCase):
    def setUp(self):
        Locale.objects.create(
            language_code=get_supported_content_language_variant(settings.LANGUAGE_CODE)
        )
        root = Page.add_root(title="Root", slug="root")
        self.home = HomePage(
            title="Home Page",
            slug="home-page",
            hero_buttons_cta="Get involved",
            hero_title="Philly Bike Action",
            hero_text="<p>Safe streets!</p>",
        )
        root.add_child(instance=self.home)
        Site.objects.create(hostname="testserver", root_page=self.home, is_default_site=True)

        self.resources = NavigationContainerPage(title="Resources", slug="resources")
        self.home.add_child(instance=self.resources)

        self.report = CmsStreamPage(title="Report Obstructions", slug="report-obstructions")
        self.resources.add_child(instance=self.report)

    def test_home_has_no_breadcrumbs(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="breadcrumbs"')

    def test_nested_cms_page(self):
        response = self.client.get("/resources/report-obstructions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<a href="/">Home</a>')
        self.assertContains(response, '<a href="/resources/">Resources</a>')
        self.assertContains(response, '<strong aria-current="page">Report Obstructions</strong>')
        self.assertNotContains(response, '<a href="/resources/report-obstructions/">')

    def test_cms_container_page(self):
        response = self.client.get("/resources/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<a href="/">Home</a>')
        self.assertContains(response, '<strong aria-current="page">Resources</strong>')

    def test_gap_segments_are_unlinked(self):
        response = self.client.get("/tools/laser/map/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<span>Tools</span>")
        self.assertContains(response, "<span>Laser</span>")
        self.assertNotContains(response, '<a href="/tools/">')
        self.assertNotContains(response, '<a href="/tools/laser/">')
        self.assertContains(response, '<strong aria-current="page">Map</strong>')

    def test_django_view_page(self):
        response = self.client.get("/events/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<a href="/">Home</a>')
        self.assertContains(response, '<strong aria-current="page">Events</strong>')

    def test_separator_is_hidden_from_screen_readers(self):
        response = self.client.get("/resources/report-obstructions/")
        self.assertContains(
            response, '<span class="breadcrumb-separator" aria-hidden="true">&gt;</span>', count=2
        )
