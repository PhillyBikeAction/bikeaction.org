import datetime

import sesame.utils
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import EventSignIn, ScheduledEvent
from events.signin_cookie import (
    EVENT_SIGNIN_COOKIE_NAME,
    EVENT_SIGNIN_COOKIE_TYPE_SIGNIN,
    EVENT_SIGNIN_COOKIE_TYPE_USER,
    decrypt_event_signin_payload,
    encrypt_event_signin_payload,
)


class EventSignInRememberedIdentityTests(TestCase):
    def make_event(self, title="Test Event"):
        starts_at = timezone.now() + datetime.timedelta(hours=1)
        return ScheduledEvent.objects.create(
            title=title,
            status=ScheduledEvent.Status.SCHEDULED,
            start_datetime=starts_at,
            end_datetime=starts_at + datetime.timedelta(hours=1),
        )

    def signin_data(self, **overrides):
        data = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "council_district": EventSignIn.District.DISTRICT_3,
            "zip_code": "19107",
            "newsletter_opt_in": "on",
        }
        data.update(overrides)
        return data

    def test_manual_anonymous_signin_sets_encrypted_signin_cookie(self):
        event = self.make_event()

        response = self.client.post(reverse("event_signin", args=[event.slug]), self.signin_data())

        self.assertEqual(response.status_code, 302)
        cookie_value = response.cookies[EVENT_SIGNIN_COOKIE_NAME].value
        payload = decrypt_event_signin_payload(cookie_value)
        signin = EventSignIn.objects.get()
        self.assertEqual(payload, {"type": EVENT_SIGNIN_COOKIE_TYPE_SIGNIN, "id": str(signin.id)})
        self.assertNotIn("Ada", cookie_value)
        self.assertNotIn("ada@example.com", cookie_value)

    def test_anonymous_cookie_prefills_form_and_quick_signs_into_next_event(self):
        first_event = self.make_event("First Event")
        second_event = self.make_event("Second Event")
        first_response = self.client.post(
            reverse("event_signin", args=[first_event.slug]), self.signin_data()
        )
        self.client.cookies[EVENT_SIGNIN_COOKIE_NAME] = first_response.cookies[
            EVENT_SIGNIN_COOKIE_NAME
        ].value

        get_response = self.client.get(reverse("event_signin", args=[second_event.slug]))
        self.assertContains(get_response, "Hello Ada, would you like to sign in?")
        self.assertContains(get_response, 'value="ada@example.com"')

        post_response = self.client.post(
            reverse("event_signin", args=[second_event.slug]), {"quick_signin": "1"}
        )

        self.assertEqual(post_response.status_code, 302)
        signin = EventSignIn.objects.get(event=second_event)
        self.assertEqual(signin.first_name, "Ada")
        self.assertEqual(signin.email, "ada@example.com")

    def test_authenticated_user_with_incomplete_data_prefills_form_without_quick_signin(self):
        event = self.make_event()
        user = User.objects.create_user(
            username="grace",
            email="grace@example.com",
            password="password",
            first_name="Grace",
            last_name="Hopper",
        )
        self.client.force_login(user)

        get_response = self.client.get(reverse("event_signin", args=[event.slug]))
        self.assertNotContains(get_response, "would you like to sign in?")
        self.assertContains(get_response, 'value="Grace"')
        self.assertContains(get_response, 'value="Hopper"')
        self.assertContains(get_response, 'value="grace@example.com"')

        response = self.client.post(
            reverse("event_signin", args=[event.slug]),
            self.signin_data(
                first_name="Grace",
                last_name="Hopper",
                email="grace@example.com",
            ),
        )

        self.assertEqual(response.status_code, 302)
        signin = EventSignIn.objects.get(event=event)
        self.assertEqual(signin.first_name, "Grace")
        self.assertEqual(signin.email, "grace@example.com")
        payload = decrypt_event_signin_payload(response.cookies[EVENT_SIGNIN_COOKIE_NAME].value)
        self.assertEqual(payload, {"type": EVENT_SIGNIN_COOKIE_TYPE_USER, "id": user.id})

    def test_manual_authenticated_signin_for_different_email_stores_signin_cookie(self):
        event = self.make_event()
        user = User.objects.create_user(
            username="grace",
            email="grace@example.com",
            password="password",
            first_name="Grace",
            last_name="Hopper",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("event_signin", args=[event.slug]),
            self.signin_data(email="someone@example.com"),
        )

        signin = EventSignIn.objects.get(event=event)
        payload = decrypt_event_signin_payload(response.cookies[EVENT_SIGNIN_COOKIE_NAME].value)
        self.assertEqual(payload, {"type": EVENT_SIGNIN_COOKIE_TYPE_SIGNIN, "id": str(signin.id)})

    def test_anonymous_user_cookie_prefills_known_user_identity_without_quick_signin(self):
        event = self.make_event()
        user = User.objects.create_user(
            username="grace",
            email="grace@example.com",
            password="password",
            first_name="Grace",
            last_name="Hopper",
        )
        self.client.cookies[EVENT_SIGNIN_COOKIE_NAME] = encrypt_event_signin_payload(
            {"type": EVENT_SIGNIN_COOKIE_TYPE_USER, "id": user.id}
        )

        get_response = self.client.get(reverse("event_signin", args=[event.slug]))
        self.assertNotContains(get_response, "would you like to sign in?")
        self.assertContains(get_response, 'value="Grace"')
        self.assertContains(get_response, 'value="Hopper"')
        self.assertContains(get_response, 'value="grace@example.com"')

    def test_anonymous_user_cookie_does_not_fall_back_to_email_localpart_as_first_name(self):
        event = self.make_event()
        user = User.objects.create_user(
            username="grace",
            email="grace@example.com",
            password="password",
            last_name="Hopper",
        )
        self.client.cookies[EVENT_SIGNIN_COOKIE_NAME] = encrypt_event_signin_payload(
            {"type": EVENT_SIGNIN_COOKIE_TYPE_USER, "id": user.id}
        )

        get_response = self.client.get(reverse("event_signin", args=[event.slug]))
        self.assertNotContains(get_response, 'value="grace"')
        self.assertContains(get_response, 'value="grace@example.com"')

    def test_invalid_cookie_is_ignored(self):
        event = self.make_event()
        self.client.cookies[EVENT_SIGNIN_COOKIE_NAME] = "not-a-valid-token"

        response = self.client.get(reverse("event_signin", args=[event.slug]))

        self.assertNotContains(response, "would you like to sign in?")

    def test_logout_clears_signin_cookie(self):
        user = User.objects.create_user(
            username="grace",
            email="grace@example.com",
            password="password",
            first_name="Grace",
            last_name="Hopper",
        )
        self.client.force_login(user)
        self.client.cookies[EVENT_SIGNIN_COOKIE_NAME] = "existing-cookie"

        response = self.client.post(reverse("account_logout"))

        self.assertEqual(response.cookies[EVENT_SIGNIN_COOKIE_NAME].value, "")
        self.assertEqual(response.cookies[EVENT_SIGNIN_COOKIE_NAME]["max-age"], 0)

    def test_login_sets_user_signin_cookie(self):
        user = User.objects.create_user(
            username="grace",
            email="grace@example.com",
            password="password",
            first_name="Grace",
            last_name="Hopper",
        )

        response = self.client.get(reverse("sesame_login") + sesame.utils.get_query_string(user))

        self.assertEqual(response.status_code, 302)
        payload = decrypt_event_signin_payload(response.cookies[EVENT_SIGNIN_COOKIE_NAME].value)
        self.assertEqual(payload, {"type": EVENT_SIGNIN_COOKIE_TYPE_USER, "id": user.id})
