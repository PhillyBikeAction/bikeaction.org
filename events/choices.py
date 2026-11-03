from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext as _


def grouped_event_choices(events, now=None):
    """Group event choices without changing the caller's visibility restrictions."""
    now = now if now is not None else timezone.now()
    recent_cutoff = now - timedelta(days=30)
    upcoming, recent, historic = [], [], []
    for event in events:
        if event.start_datetime >= now or (
            event.end_datetime is not None and event.end_datetime >= now
        ):
            upcoming.append(event)
        elif event.start_datetime >= recent_cutoff:
            recent.append(event)
        else:
            historic.append(event)

    groups = []
    for label, items, reverse in (
        (_("Current & upcoming"), upcoming, False),
        (_("Recent (past 30 days)"), recent, True),
        (_("History"), historic, True),
    ):
        if not items:
            continue
        items.sort(key=lambda event: (event.start_datetime, str(event.pk)), reverse=reverse)
        groups.append(
            (
                label,
                [
                    (
                        str(event.pk),
                        f"{timezone.localtime(event.start_datetime):%b %d, %Y} — {event.title}",
                    )
                    for event in items
                ],
            )
        )
    return groups
