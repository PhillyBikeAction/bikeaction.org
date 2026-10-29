from dataclasses import dataclass

from asgiref.sync import async_to_sync
from celery import shared_task
from django.contrib.gis.geos import Point
from django.template import engines

from facets.utils import geocode_address
from pbaabp.email import send_email_message


@dataclass(frozen=True)
class PetitionOrCampaignReference:
    """Public values an organizer can use in a petition confirmation."""

    title: str
    slug: str | None
    id: str

    def __str__(self):
        return self.title


@shared_task
def geocode_signature(signature_id):
    from campaigns.models import PetitionSignature

    signature = PetitionSignature.objects.get(id=signature_id)

    if signature.postal_address_line_1 is not None:
        print(f"Geocoding {signature}")
        address = async_to_sync(geocode_address)(
            signature.postal_address_line_1 + " " + signature.zip_code
        )
        if address is not None:
            print(f"Address found {address}")
            PetitionSignature.objects.filter(id=signature_id).update(
                location=Point(address.longitude, address.latitude)
            )
        else:
            print(f"No address found for {signature.postal_address_line_1} {signature.zip_code}")
            PetitionSignature.objects.filter(id=signature_id).update(location=None)


@shared_task
def send_post_sign_email(signature_id):
    """Send a post-sign email to the petition signer."""
    from campaigns.models import PetitionSignature

    signature = PetitionSignature.objects.select_related("petition", "petition__campaign").get(
        id=signature_id
    )
    petition = signature.petition

    if not petition.post_sign_email_enabled:
        return

    if not petition.post_sign_email_subject or not petition.post_sign_email_body:
        return

    if not signature.email:
        return

    campaign = petition.campaign
    context = {
        "first_name": signature.first_name,
        "last_name": signature.last_name,
        "email": signature.email,
        "petition": PetitionOrCampaignReference(petition.title, petition.slug, str(petition.pk)),
        "campaign": PetitionOrCampaignReference(campaign.title, campaign.slug, str(campaign.pk))
        if campaign
        else None,
    }

    # Render the subject as a Django template
    engine = engines["django"]
    subject_template = engine.from_string(petition.post_sign_email_subject)
    rendered_subject = subject_template.render(context)

    send_email_message(
        template_name="post_sign_email",
        from_=None,
        to=[signature.email],
        context=context,
        subject=rendered_subject,
        message=petition.post_sign_email_body,
    )
