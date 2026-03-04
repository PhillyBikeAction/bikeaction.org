import uuid

from django.db import models, transaction

from facets.models import RegisteredCommunityOrganization
from neighborhood_selection.tasks import update_neighborhood_role_and_channel


class Neighborhood(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    discord_role_id = models.CharField(max_length=64, null=True, blank=True)
    discord_channel_id = models.CharField(max_length=64, null=True, blank=True)
    requests = models.IntegerField(blank=False, default=0)
    approved = models.BooleanField(blank=False, default=False)
    featured = models.BooleanField(blank=False, default=False)

    name = models.CharField(max_length=512)
    rcos = models.ManyToManyField(RegisteredCommunityOrganization, blank=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            old_model = Neighborhood.objects.get(pk=self.pk)
            change_fields = [
                f.name
                for f in Neighborhood._meta._get_fields()
                if f.name not in ["id", "discord_role_id", "discord_channel_id", "requests"]
            ]
            modified = False
            for i in change_fields:
                if getattr(old_model, i, None) != getattr(self, i, None):
                    modified = True
            if modified:
                transaction.on_commit(lambda: update_neighborhood_role_and_channel.delay(self.id))
        else:
            transaction.on_commit(lambda: update_neighborhood_role_and_channel.delay(self.id))
        super(Neighborhood, self).save(*args, **kwargs)

    def __str__(self):
        return self.name
