from django.conf import settings
from django.core.management.base import BaseCommand

from events.models import EventRSVP, ScheduledEvent
from pbaabp.email import send_email_message

RSVPs = EventRSVP.objects.filter(
    event=ScheduledEvent.objects.get(title="11th Street Bike Lane Clean-up")
)
SENT = []


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        print("RSVPs!")
        for rsvp in RSVPs:
            if rsvp.user and rsvp.user.email not in SENT:
                send_email_message(
                    "11st-cleanup",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [rsvp.user.email],
                    {"first_name": rsvp.user.first_name},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(rsvp.user.email)
            elif rsvp.email and rsvp.email not in SENT:
                send_email_message(
                    "11st-cleanup",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [rsvp.email],
                    {"first_name": rsvp.first_name},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(rsvp.email)
            else:
                print(f"skipping {rsvp}")
        print(len(SENT))
