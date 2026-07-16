from celery import shared_task
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from emailblasts.models import EmailBlast, EmailBlastDelivery
from emailblasts.targeting import _email_blast_target_profiles
from emailblasts.utils import email_blast_full_body
from pbaabp.email import send_email_message
from profiles.models import DoNotEmail


@shared_task
def send_email_blast(email_blast_id):
    claimed = EmailBlast.objects.filter(
        id=email_blast_id,
        status=EmailBlast.Status.APPROVED,
    ).update(status=EmailBlast.Status.SENDING)
    if not claimed:
        status = EmailBlast.objects.filter(id=email_blast_id).values_list("status", flat=True)
        return (
            f"Email blast {email_blast_id} is {status.first() or 'missing'}; "
            "only approved blasts can be sent."
        )

    blast = EmailBlast.objects.select_related("target").get(id=email_blast_id)

    if blast.target is None:
        blast.status = EmailBlast.Status.APPROVED
        blast.save(update_fields=["status", "updated_at"])
        return f"Email blast {email_blast_id} has no target."

    body = email_blast_full_body(blast.body, blast.target.description)
    profiles = (
        _email_blast_target_profiles(blast.target)
        .select_related("user")
        .exclude(user__email__isnull=True)
        .exclude(user__email="")
    )

    sent_count = 0
    suppressed_count = 0
    for profile in profiles:
        email = profile.user.email.strip()
        email_key = email.lower()
        if DoNotEmail.objects.filter(email__iexact=email_key).exists():
            suppressed_count += 1
            continue

        try:
            with transaction.atomic():
                EmailBlastDelivery.objects.create(
                    email_blast=blast,
                    profile=profile,
                    email=email_key,
                )
        except IntegrityError:
            delivery = EmailBlastDelivery.objects.get(email_blast=blast, email=email_key)
            if delivery.sent_at is not None:
                continue

        try:
            send_email_message(
                template_name=None,
                from_=settings.DEFAULT_FROM_EMAIL,
                to=[email_key],
                context={
                    "first_name": profile.user.first_name,
                    "last_name": profile.user.last_name,
                    "name": profile.user.get_full_name(),
                    "email": email_key,
                    "target_description": blast.target.description,
                },
                subject=blast.subject,
                message=body,
                reply_to=[blast.reply_to],
            )
        except Exception:
            EmailBlastDelivery.objects.filter(email_blast=blast, email=email_key).delete()
            EmailBlast.objects.filter(
                id=email_blast_id,
                status=EmailBlast.Status.SENDING,
            ).update(status=EmailBlast.Status.APPROVED)
            raise

        EmailBlastDelivery.objects.filter(email_blast=blast, email=email_key).update(
            sent_at=timezone.now()
        )
        sent_count += 1

    blast.status = EmailBlast.Status.SENT
    blast.save(update_fields=["status", "updated_at"])

    return (
        f"Sent email blast {email_blast_id} to {sent_count} profiles; "
        f"skipped {suppressed_count} suppressed recipients."
    )
