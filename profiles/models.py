import uuid

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models, transaction

from profiles.tasks import sync_to_mailchimp


class Profile(models.Model):
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
    mailchimp_contact_id = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

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

    @property
    def discord(self):
        return self.user.socialaccount_set.filter(provider="discord").first()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            old_model = Profile.objects.get(pk=self.pk)
            change_fields = [
                f.name for f in Profile._meta._get_fields() if f.name in ["newsletter_opt_in"]
            ]
            modified = False
            for i in change_fields:
                if getattr(old_model, i, None) != getattr(self, i, None):
                    modified = True
            if modified:
                transaction.on_commit(lambda: sync_to_mailchimp.delay(self.id))
        else:
            transaction.on_commit(lambda: sync_to_mailchimp.delay(self.id))
        super(Profile, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.user.email}"


class NewsletterSignup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mailchimp_contact_id = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    first_name = models.CharField("first name", max_length=150, blank=True)
    last_name = models.CharField("last name", max_length=150, blank=True)
    email = models.EmailField("email address", blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"


class ShirtInterest(models.Model):
    class Fit(models.IntegerChoices):
        ALTERNATIVE_01070C = 0, 'Unisex Classic Fit - "Go-To T-Shirt"'
        ALTERNATIVE_5114C1 = (
            1,
            "Women's Relaxed Fit - \"Women's Go-To Headliner Cropped Tee\"",
        )

    class Size(models.IntegerChoices):
        XS = -2, "XS"
        S = -1, "S"
        M = 0, "M"
        L = 1, "L"
        XL = 2, "XL"
        XXL = 3, "2XL"

    class PrintColor(models.IntegerChoices):
        PINK = 0, "Pink"
        GREEN = 1, "Green"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tshirt_requests")

    fit = models.IntegerField(null=False, blank=False, choices=Fit.choices)
    size = models.IntegerField(null=False, blank=False, choices=Size.choices)
    print_color = models.IntegerField(null=False, blank=False, choices=PrintColor.choices)
