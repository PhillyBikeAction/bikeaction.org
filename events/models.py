import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.urls import reverse
from icalendar import Calendar, Event
from interactions.models.discord.enums import ScheduledEventStatus

from events.tasks import sync_to_mailjet
from lib.slugify import unique_slugify


class ScheduledEvent(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled"
        ACTIVE = "active"
        COMPLETED = "completed"
        CANCELED = "canceled"
        DELETED = "deleted"
        UNKNOWN = "unknown"

    @classmethod
    def get_status(cls, discord_status):
        _mapping = {
            ScheduledEventStatus.SCHEDULED: cls.Status.SCHEDULED,
            ScheduledEventStatus.ACTIVE: cls.Status.ACTIVE,
            ScheduledEventStatus.COMPLETED: cls.Status.COMPLETED,
            ScheduledEventStatus.CANCELED: cls.Status.CANCELED,
        }
        return _mapping.get(discord_status, cls.Status.UNKNOWN)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    discord_id = models.CharField(max_length=64, null=True, blank=True)
    slug = models.SlugField(max_length=512, null=True, blank=True)
    hidden = models.BooleanField(blank=False, default=False)

    title = models.CharField(max_length=512)
    status = models.CharField(max_length=16, choices=Status.choices)
    description = models.TextField(null=True, blank=True)
    cover = models.URLField(null=True, blank=True)
    location = models.CharField(max_length=512, null=True, blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(null=True, blank=True)

    def ics(self):
        _calendar = Calendar()
        _calendar.add("prodid", "-//Philly Bike Action//PBA Events//EN")
        _calendar.add("version", "2.0")

        _event = Event()
        _event["uid"] = self.id
        _event.add("summary", self.title)
        _event.add("description", self.description)
        _event.add("dtstart", self.start_datetime)
        _event.add("dtend", self.end_datetime)
        _event.add("location", self.location)
        _event.add("url", settings.SITE_URL + reverse("event_detail", args=[self.slug]))

        _calendar.add_component(_event)

        return _calendar.to_ical().decode()

    def save(self, *args, **kwargs):
        if self.slug is None:
            unique_slugify(self, self.title)
        super(ScheduledEvent, self).save(*args, **kwargs)

    def __str__(self):
        return self.title


class EventRSVP(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(ScheduledEvent, to_field="id", on_delete=models.CASCADE)

    user = models.ForeignKey(
        User, related_name="event_rsvps", blank=True, null=True, on_delete=models.CASCADE
    )

    first_name = models.CharField(max_length=64, null=True, blank=True)
    last_name = models.CharField(max_length=64, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)


class EventSignIn(models.Model):
    class District(models.IntegerChoices):
        NO_DISTRICT = 0, "N/A - I do not live in Philadelphia"
        DISTRICT_1 = 1, "District 1"
        DISTRICT_2 = 2, "District 2"
        DISTRICT_3 = 3, "District 3"
        DISTRICT_4 = 4, "District 4"
        DISTRICT_5 = 5, "District 5"
        DISTRICT_6 = 6, "District 6"
        DISTRICT_7 = 7, "District 7"
        DISTRICT_8 = 8, "District 8"
        DISTRICT_9 = 9, "District 9"
        DISTRICT_10 = 10, "District 10"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(ScheduledEvent, to_field="id", on_delete=models.CASCADE)
    mailjet_contact_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    first_name = models.CharField(max_length=64, null=False, blank=False)
    last_name = models.CharField(max_length=64, null=False, blank=False)
    email = models.EmailField(null=False, blank=False)
    council_district = models.IntegerField(null=False, blank=False, choices=District.choices)
    zip_code = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^(^[0-9]{5}(?:-[0-9]{4})?$|^$)",
                message="Must be a valid zipcode in formats 19107 or 19107-3200",
            )
        ],
        null=True,
        blank=True,
    )
    newsletter_opt_in = models.BooleanField(blank=False, default=False)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            old_model = EventSignIn.objects.get(pk=self.pk)
            change_fields = [
                f.name
                for f in EventSignIn._meta._get_fields()
                if f.name not in ["id", "event", "mailjet_contact_id"]
            ]
            modified = False
            for i in change_fields:
                if getattr(old_model, i, None) != getattr(self, i, None):
                    modified = True
            if modified:
                transaction.on_commit(lambda: sync_to_mailjet.delay(self.id))
        else:
            transaction.on_commit(lambda: sync_to_mailjet.delay(self.id))
        super(EventSignIn, self).save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.first_name} {self.last_name} - "
            f"{self.event} - {self.event.start_datetime.strftime('%Y-%m-%d')}"
        )
