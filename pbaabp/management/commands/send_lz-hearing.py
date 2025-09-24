from django.conf import settings
from django.core.management.base import BaseCommand

from facets.models import District
from pbaabp.email import send_email_message
from profiles.models import Profile

district1 = District.objects.get(name="District 1")
district2 = District.objects.get(name="District 2")
district3 = District.objects.get(name="District 3")
district5 = District.objects.get(name="District 5")

SENT = []
SENT_D1 = []
SENT_D2 = []
SENT_D3 = []
SENT_D5 = []


class Command(BaseCommand):

    def handle(*args, **kwargs):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in Profile.objects.all():
            if profile.user.email not in SENT and profile.location is not None:
                if district1.mpoly.contains(profile.location):
                    send_email_message(
                        "lz-hearing/d1-d2-d5",
                        "Philly Bike Action <noreply@bikeaction.org>",
                        [profile.user.email],
                        {
                            "first_name": profile.user.first_name,
                        },
                        reply_to=["info@bikeaction.org"],
                    )
                    SENT_D1.append(profile.user.email.lower())
                    SENT.append(profile.user.email.lower())
                elif district2.mpoly.contains(profile.location):
                    send_email_message(
                        "lz-hearing/d1-d2-d5",
                        "Philly Bike Action <noreply@bikeaction.org>",
                        [profile.user.email],
                        {
                            "first_name": profile.user.first_name,
                        },
                        reply_to=["info@bikeaction.org"],
                    )
                    SENT_D2.append(profile.user.email.lower())
                    SENT.append(profile.user.email.lower())
                elif district5.mpoly.contains(profile.location):
                    send_email_message(
                        "lz-hearing/d1-d2-d5",
                        "Philly Bike Action <noreply@bikeaction.org>",
                        [profile.user.email],
                        {
                            "first_name": profile.user.first_name,
                        },
                        reply_to=["info@bikeaction.org"],
                    )
                    SENT_D5.append(profile.user.email.lower())
                    SENT.append(profile.user.email.lower())
                elif district3.mpoly.contains(profile.location):
                    send_email_message(
                        "lz-hearing/d3",
                        "Philly Bike Action <noreply@bikeaction.org>",
                        [profile.user.email],
                        {
                            "first_name": profile.user.first_name,
                        },
                        reply_to=["info@bikeaction.org"],
                    )
                    SENT_D3.append(profile.user.email.lower())
                    SENT.append(profile.user.email.lower())
                else:
                    print(f"skipping {profile}")
            else:
                print(f"skipping {profile}")

        print(f"Sent {len(SENT)}")
        print(f"  - D1 profiles: {len(SENT_D1)}")
        print(f"  - D2 profiles: {len(SENT_D2)}")
        print(f"  - D5 profiles: {len(SENT_D5)}")
        print(f"  - D3 profiles: {len(SENT_D3)}")
