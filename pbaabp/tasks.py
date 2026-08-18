from urllib.parse import urlparse

import sesame.utils
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.test import RequestFactory
from django.urls import reverse
from easy_thumbnails.files import generate_all_aliases

from pbaabp.email import send_email_message
from pbaabp.integrations.mailjet import Mailjet
from profiles.forms import BaseProfileSignupForm

BASE_MESSAGE = """
We created your PBA account as requested!

Follow the link below to set a password for your account.
"""

SUBSCRIPTION_MESSAGE = """
We created your PBA account so that you can manage your
new recurring donation to Philly Bike Action. Follow the link below to
set a password for your account.
"""


@shared_task
@transaction.atomic
def create_pba_account(
    first_name=None,
    last_name=None,
    street_address=None,
    zip_code=None,
    email=None,
    newsletter_opt_in=True,
    subscription=False,
    _return=False,
):
    parsed = urlparse(settings.SITE_URL)
    factory = RequestFactory(headers={"Host": parsed.netloc})
    request = factory.get("/")
    request._scheme = parsed.scheme
    request.session = {}
    message = BASE_MESSAGE if not subscription else SUBSCRIPTION_MESSAGE
    form = BaseProfileSignupForm(
        {
            "first_name": first_name,
            "last_name": last_name,
            "street_address": street_address,
            "zip_code": zip_code,
            "email": email,
            "username": email,
            "newsletter_opt_in": newsletter_opt_in,
            "password1": "Password@99",
            "password2": "Password@99",
        }
    )
    if form.is_valid():
        user = form.save(request)
        user.set_unusable_password()
        user.save()
        link = reverse("sesame_login")
        link = request.build_absolute_uri(link)
        link += sesame.utils.get_query_string(user)
        link += f"&next={reverse('account_set_password')}"
        subject = f"Welcome! Create a password for {request.get_host()}"
        message = f"""\
Hello {user.first_name},

{message}

* [Create your password]({link})

NOTE: This link will expire in 7 days!

Thank you for being a part of the action!
"""
        send_email_message(None, None, [user.email], None, message=message, subject=subject)
        if _return:
            return user

    if _return:
        return None


@shared_task
def subscribe_to_newsletter(email, first_name=None, last_name=None, tags=None):
    name = ""
    if first_name:
        name += first_name
    if last_name:
        name += f" {last_name}"
    mailjet = Mailjet()
    mailjet.fetch_contact(email)
    mailjet.update_contact_data(
        email,
        {
            "first_name": first_name,
            "last_name": last_name,
            "name": name,
        },
    )
    mailjet.add_contact_to_list(email, subscribed=True)


@shared_task
def generate_thumbnails(app_name, object_name, pk, field):
    model = apps.get_model(app_name, object_name)
    instance = model._default_manager.get(pk=pk)
    fieldfile = getattr(instance, field)
    generate_all_aliases(fieldfile, include_global=True)
