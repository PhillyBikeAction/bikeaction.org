from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from maillinks.admin import OrganizerMailLinkAdmin
from maillinks.models import MailLink
from pbaabp.admin import organizer_admin
from profiles.models import Profile

User = get_user_model()


def _patch_is_organizer(value):
    return patch.object(Profile, "is_organizer", new_callable=PropertyMock, return_value=value)


class OrganizerMailLinkAdminTests(SimpleTestCase):
    def setUp(self):
        self.model_admin = organizer_admin._registry[MailLink]
        self.request = RequestFactory().get("/organizer/maillinks/maillink/")

    def set_organizer(self, is_organizer):
        self.request.user = SimpleNamespace(
            is_authenticated=True,
            profile=SimpleNamespace(is_organizer=is_organizer),
        )

    def test_mail_links_are_registered_in_organizer_admin(self):
        self.assertIsInstance(self.model_admin, OrganizerMailLinkAdmin)

    def test_organizers_can_view_create_and_change_but_not_delete(self):
        self.set_organizer(True)

        self.assertTrue(self.model_admin.has_view_permission(self.request))
        self.assertTrue(self.model_admin.has_add_permission(self.request))
        self.assertTrue(self.model_admin.has_change_permission(self.request))
        self.assertFalse(self.model_admin.has_delete_permission(self.request))

    def test_non_organizers_do_not_receive_mail_link_permissions(self):
        self.set_organizer(False)

        self.assertFalse(self.model_admin.has_view_permission(self.request))
        self.assertFalse(self.model_admin.has_add_permission(self.request))
        self.assertFalse(self.model_admin.has_change_permission(self.request))
        self.assertFalse(self.model_admin.has_delete_permission(self.request))


class MailLinkActiveAccessTests(TestCase):
    def setUp(self):
        self.active_maillink = MailLink.objects.create(
            active=True,
            title="Active Test MailLink",
            slug="active-test",
            to="target@example.com",
            subject="Active Subject",
            body="Active body",
        )
        self.inactive_maillink = MailLink.objects.create(
            active=False,
            title="Inactive Test MailLink",
            slug="inactive-test",
            to="target@example.com",
            subject="Inactive Subject",
            body="Inactive body",
        )
        self.user = User.objects.create_user(
            username="user", email="user@example.com", password="pw"
        )
        Profile.objects.create(user=self.user)

    def _urls_for(self, maillink):
        return [
            reverse("maillink_view", kwargs={"slug": maillink.slug}),
            reverse("maillink_flyer", kwargs={"slug": maillink.slug}),
            reverse("maillink_send", kwargs={"slug": maillink.slug}),
        ]

    def test_active_maillinks_are_public(self):
        for url in self._urls_for(self.active_maillink):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, [200, 303])

    def test_inactive_maillinks_are_hidden_from_anonymous_users(self):
        for url in self._urls_for(self.inactive_maillink):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)

    def test_inactive_maillinks_are_hidden_from_non_organizers(self):
        self.client.force_login(self.user)
        with _patch_is_organizer(False):
            for url in self._urls_for(self.inactive_maillink):
                with self.subTest(url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 404)

    def test_inactive_maillinks_are_visible_to_organizers(self):
        self.client.force_login(self.user)
        with _patch_is_organizer(True):
            for url in self._urls_for(self.inactive_maillink):
                with self.subTest(url=url):
                    response = self.client.get(url)
                    self.assertIn(response.status_code, [200, 303])
