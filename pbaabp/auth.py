from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from campaigns.models import Campaign
from profiles.models import Profile

User = get_user_model()

ORGANIZER_MODELS = [Campaign, User, Profile]
ORGANIZER_PERMS = [
    f"{model._meta.app_label}.view_{model._meta.model_name}" for model in ORGANIZER_MODELS
]


class OrganizerAdminBackend(BaseBackend):
    def has_perm(self, user_obj, perm, obj=None):
        if user_obj.is_authenticated and user_obj.profile.is_organizer and perm in ORGANIZER_PERMS:
            return True
        return False
