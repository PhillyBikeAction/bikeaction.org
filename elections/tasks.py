from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from elections.models import Nomination, get_user_display_name
from pbaabp.email import send_email_message


@shared_task
def send_nomination_notification(nomination_id):
    """Send email notification to nominee for a specific nomination."""

    try:
        nomination = Nomination.objects.select_related(
            "nominee__user", "nominee__election", "nominator"
        ).get(id=nomination_id)
    except Nomination.DoesNotExist:
        return f"Nomination {nomination_id} not found"

    user = nomination.nominee.user
    election = nomination.nominee.election
    nominator = nomination.nominator

    # Build the respond URL
    respond_path = reverse(
        "nomination_respond",
        kwargs={"election_slug": election.slug, "pk": nomination.id},
    )
    respond_url = f"{settings.SITE_URL}{respond_path}"
    nominations_close = timezone.localtime(election.nominations_close)
    acceptance_deadline = timezone.localtime(election.nominations_close + timedelta(hours=24))

    # Prepare email message
    message = f"""
You have been nominated for **{election.title}**!

**Nominated by:** {get_user_display_name(nominator)}

Please respond to this nomination by visiting:

[Respond to Nomination]({respond_url})

**Before accepting, nominate yourself and submit your own nomination statement.**
The response page links to the nomination form. Once you have submitted your
self-nomination and completed your nominee profile, return to accept this nomination.
If you have already submitted a self-nomination with your own statement, you do not
need to submit another one.

You can decline this nomination without nominating yourself.

Your self-nomination confirms that you want to run for the board and makes your
own statement public. Accepting this nomination also makes the statement below
public as an endorsement.

If more than one person has nominated you, you can accept as many endorsements
as you want to appear publicly alongside your candidacy.

You have until 24 hours after nominations close to respond. If someone has already
nominated you, you can also complete your self-nomination during that period.

**Important Dates:**

- Nominations close: {nominations_close.strftime("%B %d, %Y at %I:%M %p %Z")}
- Deadline to respond: {acceptance_deadline.strftime("%B %d, %Y at %I:%M %p %Z")}
- Voting opens: {timezone.localtime(election.voting_opens).strftime("%B %d, %Y")}

---

**Nomination Statement:**

{nomination.nomination_statement}

---

Thank you for your participation!
"""

    # Send email using the standard utility
    send_email_message(
        template_name=None,
        from_=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        context={},
        subject=f"You've been nominated for {election.title}",
        message=message,
    )

    return f"Sent nomination notification to {user.email} for {election.title}"
