import time

from celery import shared_task
from django.conf import settings
from mailchimp3 import MailChimp, helpers
from mailchimp3.mailchimpclient import MailChimpError


@shared_task
def sync_to_mailchimp(profile_id):
    time.sleep(1)  # Wait for txn that initiated this task to settle

    from profiles.models import Profile

    mailchimp = MailChimp(mc_api=settings.MAILCHIMP_API_KEY)
    profile = Profile.objects.get(id=profile_id)

    if profile.newsletter_opt_in:
        print("creating contact...")
        response = mailchimp.lists.members.create_or_update(
            settings.MAILCHIMP_AUDIENCE_ID,
            helpers.get_subscriber_hash(profile.user.email),
            {
                "email_address": profile.user.email,
                "status_if_new": "subscribed",
                "status": "subscribed",
                "merge_fields": {
                    "FNAME": profile.user.first_name,
                    "LNAME": profile.user.last_name,
                },
            },
        )
        profile.mailchimp_contact_id = response["id"]
        profile.save()

        print("updating tags...")
        mailchimp.lists.members.tags.update(
            settings.MAILCHIMP_AUDIENCE_ID,
            helpers.get_subscriber_hash(profile.user.email),
            data={
                "tags": [
                    {"name": "apps", "status": "active"},
                    {"name": f"district-{profile.council_district}", "status": "active"},
                    {"name": "apps_opt_out", "status": "inactive"},
                ]
            },
        )

    else:
        try:
            response = mailchimp.lists.members.get(
                settings.MAILCHIMP_AUDIENCE_ID, helpers.get_subscriber_hash(profile.user.email)
            )
            contact_id = response["id"]
        except MailChimpError:
            contact_id = None

        if contact_id is not None:
            print("unsubscribing contact...")
            response = mailchimp.lists.members.create_or_update(
                settings.MAILCHIMP_AUDIENCE_ID,
                helpers.get_subscriber_hash(profile.user.email),
                {
                    "email_address": profile.user.email,
                    "status_if_new": "unsubscribed",
                    "status": "unsubscribed",
                    "merge_fields": {
                        "FNAME": profile.user.first_name,
                        "LNAME": profile.user.last_name,
                    },
                },
            )
            profile.mailchimp_contact_id = response["id"]
            profile.save()

            print("updating tags...")
            mailchimp.lists.members.tags.update(
                settings.MAILCHIMP_AUDIENCE_ID,
                helpers.get_subscriber_hash(profile.user.email),
                data={
                    "tags": [
                        {"name": "apps", "status": "active"},
                        {"name": f"district-{profile.council_district}", "status": "active"},
                        {"name": "apps_opt_out", "status": "active"},
                    ]
                },
            )
