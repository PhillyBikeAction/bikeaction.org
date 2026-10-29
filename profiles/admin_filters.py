from django.contrib import admin

from profiles.models import Affiliation


class AffiliationFilter(admin.SimpleListFilter):
    title = "Affiliation"
    parameter_name = "affiliation"

    def lookups(self, request, model_admin):
        return [
            (str(pk), name)
            for pk, name in Affiliation.objects.filter(targetable=True).values_list("pk", "name")
        ]

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        if self.value() not in dict(self.lookup_choices):
            return queryset.none()
        return queryset.filter(affiliations=self.value())
