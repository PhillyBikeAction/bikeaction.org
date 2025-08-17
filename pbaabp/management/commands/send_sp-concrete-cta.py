from urllib.parse import urlencode

from django.conf import settings
from django.core.management.base import BaseCommand

from facets.models import District, RegisteredCommunityOrganization
from pbaabp.email import send_email_message
from profiles.models import Profile

district1 = District.objects.get(name="District 1").contained_profiles.all()
district2 = District.objects.get(name="District 2").contained_profiles.all()
ccra = RegisteredCommunityOrganization.objects.get(
    name="Center City Residents Association (CCRA)"
).contained_profiles.all()
profiles = Profile.objects.all()

SENT = []
SENT_D1 = []
SENT_D2_WITHOUT_CCRA = []
SENT_CCRA = []
SENT_REMAINDER = []


class Command(BaseCommand):

    def handle(*args, **kwargs):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if profile.user.email not in SENT:
                if profile in ccra:
                    send_email_message(
                        "sp-concrete-cta/ccra",
                        "Philly Bike Action <noreply@bikeaction.org>",
                        [profile.user.email],
                        {
                            "first_name": profile.user.first_name,
                            "maillinks_params": urlencode(
                                {
                                    "first_name": profile.user.first_name,
                                    "last_name": profile.user.last_name,
                                    "address": profile.street_address,
                                }
                            ),
                        },
                        reply_to=["info@bikeaction.org"],
                    )
                    SENT.append(profile.user.email.lower())
                    SENT_CCRA.append(profile.user.email.lower())
                elif profile in district2:
                    send_email_message(
                        "sp-concrete-cta/d2-wo-ccra",
                        "Philly Bike Action <noreply@bikeaction.org>",
                        [profile.user.email],
                        {
                            "first_name": profile.user.first_name,
                            "maillinks_params": urlencode(
                                {
                                    "first_name": profile.user.first_name,
                                    "last_name": profile.user.last_name,
                                    "address": profile.street_address,
                                }
                            ),
                        },
                        reply_to=["info@bikeaction.org"],
                    )
                    SENT.append(profile.user.email.lower())
                    SENT_D2_WITHOUT_CCRA.append(profile.user.email.lower())
                elif profile in district1:
                    send_email_message(
                        "sp-concrete-cta/d1",
                        "Philly Bike Action <noreply@bikeaction.org>",
                        [profile.user.email],
                        {
                            "first_name": profile.user.first_name,
                            "maillinks_params": urlencode(
                                {
                                    "first_name": profile.user.first_name,
                                    "last_name": profile.user.last_name,
                                    "address": profile.street_address,
                                }
                            ),
                        },
                        reply_to=["info@bikeaction.org"],
                    )
                    SENT.append(profile.user.email.lower())
                    SENT_D1.append(profile.user.email.lower())
                else:
                    send_email_message(
                        "sp-concrete-cta/d3-10",
                        "Philly Bike Action <noreply@bikeaction.org>",
                        [profile.user.email],
                        {
                            "first_name": profile.user.first_name,
                            "maillinks_params": urlencode(
                                {
                                    "first_name": profile.user.first_name,
                                    "last_name": profile.user.last_name,
                                    "address": profile.street_address,
                                }
                            ),
                        },
                        reply_to=["info@bikeaction.org"],
                    )
                    SENT.append(profile.user.email.lower())
                    SENT_REMAINDER.append(profile.user.email.lower())
            else:
                print(f"skipping {profile}")

        print(f"Sent {len(SENT)}")
        print(f"  - CCRA: {len(SENT_CCRA)}")
        print(f"  - D2 excl CCRA: {len(SENT_D2_WITHOUT_CCRA)}")
        print(f"  - D1: {len(SENT_D1)}")
        print(f"  - D3-D10: {len(SENT_REMAINDER)}")
