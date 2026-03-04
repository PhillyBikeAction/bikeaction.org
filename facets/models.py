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

    def __lt__(self, other):
        if other is None:
            return False
        return self.name < other.name

    def __gt__(self, other):
        if other is None:
            return True
        return self.name > other.name


class District(Facet):
    intersecting_rcos = Relationship(
        to="facets.registeredcommunityorganization", predicate=Q(mpoly__intersects=L("mpoly"))
    )

    targetable = models.BooleanField(default=True)
    organizers = models.ManyToManyField(
        "profiles.Profile", related_name="organized_districts", blank=True
    )


class RegisteredCommunityOrganization(Facet):
    intersecting_zips = Relationship(to="facets.zipcode", predicate=Q(mpoly__intersects=L("mpoly")))
    intersecting_districts = Relationship(
        to="facets.district", predicate=Q(mpoly__intersects=L("mpoly"))
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


class CongressionalDistrict(Facet):
    pass


class Ward(Facet):
    class Meta:
        verbose_name = "Political Ward"
        verbose_name_plural = "Political Wards"


class Division(Facet):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="divisions", null=True)
    polling_place_name = models.CharField(max_length=256, blank=True, default="")
    polling_place_address = models.CharField(max_length=256, blank=True, default="")
    polling_place_zip = models.CharField(max_length=10, blank=True, default="")
    polling_place_accessibility = models.CharField(max_length=2, blank=True, default="")
    polling_place_parking = models.CharField(max_length=2, blank=True, default="")

    class Meta:
        verbose_name = "Political Division"
        verbose_name_plural = "Political Divisions"
