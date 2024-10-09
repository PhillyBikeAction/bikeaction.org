import uuid

from django.contrib.gis.db import models
from django.db.models import Q
from relativity.fields import L, Relationship


class Facet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    mpoly = models.MultiPolygonField()
    properties = models.JSONField()

    targetable = models.BooleanField(default=False)

    contained_profiles = Relationship(
        to="profiles.profile", predicate=Q(location__within=L("mpoly"))
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Custom(Facet):
    properties = models.JSONField(null=True, blank=True)


class District(Facet):
    targetable = models.BooleanField(default=True)


class RegisteredCommunityOrganization(Facet):
    intersecting_zips = Relationship(
        to="facets.zipcode", predicate=Q(mpoly__intersects=L("mpoly"))
    )

    @property
    def zips(self):
        return [
            z
            for z in self.intersecting_zips.all()
            if z.mpoly.intersection(self.mpoly).area / self.mpoly.area > 0.001
        ]


class ZipCode(Facet):
    intersecting_rcos = Relationship(
        to="facets.registeredcommunityorganization", predicate=Q(mpoly__intersects=L("mpoly"))
    )


class StateHouseDistrict(Facet):
    pass


class StateSenateDistrict(Facet):
    pass
