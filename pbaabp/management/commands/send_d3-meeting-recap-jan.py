from django.core.management.base import BaseCommand

from events.models import EventRSVP, EventSignIn, ScheduledEvent
from pbaabp.email import send_email_message

SENT = []


class Command(BaseCommand):
    def handle(self, *args, **options):
        event = ScheduledEvent.objects.get(slug="pba-d3-monthly-meeting")

        sign_ins = EventSignIn.objects.filter(event=event)
        rsvps = EventRSVP.objects.filter(event=event).select_related("user")

        for sign_in in sign_ins:
            if sign_in.email.lower() not in SENT:
                send_email_message(
                    "d3-meeting-recap-jan",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [sign_in.email],
                    {
                        "first_name": sign_in.first_name,
                        "last_name": sign_in.last_name,
                    },
                    reply_to=["district3@bikeaction.org"],
                )
                SENT.append(sign_in.email.lower())
                self.stdout.write(f"Sent to {sign_in.email} (sign-in)")
            else:
                self.stdout.write(f"Skipping duplicate: {sign_in.email}")

        for rsvp in rsvps:
            if rsvp.user:
                email = rsvp.user.email
                first_name = rsvp.user.first_name or rsvp.first_name or ""
                last_name = rsvp.user.last_name or rsvp.last_name or ""
            else:
                email = rsvp.email
                first_name = rsvp.first_name or ""
                last_name = rsvp.last_name or ""

            if email and email.lower() not in SENT:
                send_email_message(
                    "d3-meeting-recap-jan",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [email],
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                    },
                    reply_to=["district3@bikeaction.org"],
                )
                SENT.append(email.lower())
                self.stdout.write(f"Sent to {email} (RSVP)")
            elif email:
                self.stdout.write(f"Skipping duplicate: {email}")

        self.stdout.write(self.style.SUCCESS(f"Sent {len(SENT)} emails total"))
