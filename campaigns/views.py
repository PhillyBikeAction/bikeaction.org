import uuid

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.generic import DetailView, ListView

from campaigns.forms import PetitionSignatureForm
from campaigns.models import Campaign, Petition, PetitionSignature


def _fetch_petition_by_slug_or_id(petition_slug_or_id):
    try:
        uuid.UUID(petition_slug_or_id)
        petition_by_id = Petition.objects.filter(id=petition_slug_or_id).first()
    except ValueError:
        petition_by_id = None
    petition_by_slug = Petition.objects.filter(slug=petition_slug_or_id).first()

    if petition_by_id is not None:
        return petition_by_id
    elif petition_by_slug is not None:
        return petition_by_slug
    else:
        return None


class CampaignDetailView(DetailView):
    model = Campaign


class CampaignListView(ListView):
    model = Campaign


def petition_signatures(request, petition_slug_or_id):
    petition = _fetch_petition_by_slug_or_id(petition_slug_or_id)
    if petition is None:
        raise Http404
    return render(request, "campaigns/_partial_signatures.html", {"petition": petition})


def sign_petition(request, petition_slug_or_id):
    petition = _fetch_petition_by_slug_or_id(petition_slug_or_id)
    if petition is None:
        raise Http404
    if request.method == "POST":
        form = PetitionSignatureForm(request.POST, petition=petition)
        if form.is_valid():
            # Check for existing signature
            existing_signature = PetitionSignature.objects.filter(
                email__iexact=form.instance.email
            ).first()
            form.instance.petition = petition
            form.save()
            if petition.send_email and form.cleaned_data.get("send_email", False):
                if not existing_signature:
                    email_body = petition.email_body + "\n\n"
                    if petition.email_include_comment and form.instance.comment:
                        email_body += form.instance.comment + "\n\n"
                    email_body += f"- {form.instance.first_name} {form.instance.last_name}"
                    email = EmailMessage(
                        subject=petition.email_subject,
                        body=email_body,
                        from_email=(
                            f"{form.instance.first_name} {form.instance.last_name} "
                            f"<{settings.DEFAULT_FROM_EMAIL}>"
                        ),
                        to=petition.email_to,
                        cc=petition.email_cc,
                        reply_to=[form.instance.email],
                    )
                    email.send()
            message = "Signature captured!"
            if petition.send_email and form.cleaned_data.get("send_email", False):
                message += " E-Mail sent!"
            messages.add_message(request, messages.SUCCESS, message)
            if petition.campaign:
                return redirect("campaign", slug=petition.campaign.slug)
            else:
                return redirect("index")

    else:
        form = PetitionSignatureForm(petition=petition)

    return render(request, "petition/sign.html", context={"petition": petition, "form": form})
