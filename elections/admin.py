from django.contrib import admin
from django.utils import timezone

from elections.models import Election


class ElectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "eligibility_open",
        "eligibility_closed",
        "nominations_open_status",
        "nominations_closed_status",
        "voting_open_status",
        "voting_closed_status",
    )
    search_fields = ("title", "description")
    ordering = ("-membership_eligibility_deadline",)

    def eligibility_open(self, obj):
        return timezone.now() < obj.membership_eligibility_deadline

    eligibility_open.boolean = True
    eligibility_open.short_description = "Eligibility Open"

    def eligibility_closed(self, obj):
        return timezone.now() >= obj.membership_eligibility_deadline

    eligibility_closed.boolean = True
    eligibility_closed.short_description = "Eligibility Closed"

    def nominations_open_status(self, obj):
        now = timezone.now()
        return obj.nominations_open <= now < obj.nominations_close

    nominations_open_status.boolean = True
    nominations_open_status.short_description = "Nominations Open"

    def nominations_closed_status(self, obj):
        return timezone.now() >= obj.nominations_close

    nominations_closed_status.boolean = True
    nominations_closed_status.short_description = "Nominations Closed"

    def voting_open_status(self, obj):
        now = timezone.now()
        return obj.voting_opens <= now < obj.voting_closes

    voting_open_status.boolean = True
    voting_open_status.short_description = "Voting Open"

    def voting_closed_status(self, obj):
        return timezone.now() >= obj.voting_closes

    voting_closed_status.boolean = True
    voting_closed_status.short_description = "Voting Closed"


admin.site.register(Election, ElectionAdmin)
