import sesame.utils
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.urls import reverse

from pbaabp.email import send_email_message
from profiles.models import Profile


class Command(BaseCommand):
    def handle(self, *args, **options):
        for profile in Profile.objects.filter(
            Q(street_address__isnull=True) | Q(zip_code__isnull=True)
        ):
            link = reverse("sesame_login")
            link = f"https://apps.bikeaction.org{link}"
            link += sesame.utils.get_query_string(profile.user)
            link += f"&next={reverse('profile_update')}"
            send_email_message(
                "profile_incomplete",
                "Philly Bike Action <noreply@apps.bikeaction.org>",
                [profile.user.email],
                {"profile": profile, "sesame_url": link},
                reply_to=["apps@bikeaction.org"],
            )
