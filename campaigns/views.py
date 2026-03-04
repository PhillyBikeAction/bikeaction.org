import uuid
from datetime import datetime
from datetime import timezone as dt_timezone
from urllib.parse import quote, urlencode

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.http import Http404, HttpResponse
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

    since_param = request.GET.get("since")
    if since_param:
        # Incremental update: return only new signatures since timestamp
        try:
            since_ts = float(since_param)
            since_dt = datetime.fromtimestamp(since_ts, tz=dt_timezone.utc)
        except (ValueError, OSError):
            raise Http404

        new_signatures = petition.signatures.filter(created_at__gt=since_dt, visible=True).order_by(
            "-created_at"
        )

        # Return signature cards + OOB updates for count/progress
        return render(
            request,
            "campaigns/_partial_signatures_update.html",
            {
                "petition": petition,
                "new_signatures": new_signatures,
            },
        )

    # Full render on initial load
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

            checkbox_responses = {}
            for checkbox in petition.checkboxes.all():
                field_name = f"checkbox_{checkbox.id}"
                if field_name in form.cleaned_data:
                    checkbox_responses[checkbox.label] = form.cleaned_data[field_name]
            form.instance.checkbox_responses = checkbox_responses

            form.save()

            email_body = ""
            if petition.email_body:
                email_body += petition.email_body + "\n\n"
            if petition.email_include_comment and form.instance.comment:
                email_body += form.instance.comment + "\n\n"
            email_body += f"- {form.instance.first_name} {form.instance.last_name}"

            if petition.send_email and form.cleaned_data.get("send_email", False):
                if not existing_signature:
                    email = EmailMessage(
                        subject=petition.email_subject,
                        body=email_body,
                        from_email=(
                            f"{form.instance.first_name} {form.instance.last_name} "
                            f"<{settings.DEFAULT_FROM_EMAIL}>"
                        ),
                        to=petition.email_to.splitlines(),
                        cc=petition.email_cc.splitlines(),
                        reply_to=[form.instance.email],
                    )
                    email.send()
            message = "Signature captured!"
            if petition.send_email and form.cleaned_data.get("send_email", False):
                message += " E-Mail sent!"
            elif petition.mailto_send:
                subject = petition.email_subject
                body = email_body

                if (
                    petition.PetitionSignatureChoices.PHONE in petition.signature_fields
                    and form.instance.phone_number
                ):
                    body += f"\n{form.instance.phone_number}\n"

                if (
                    petition.PetitionSignatureChoices.ADDRESS_LINE_1 in petition.signature_fields
                    and form.instance.postal_address_line_1
                ):
                    body += f"\n{form.instance.postal_address_line_1}"
                if (
                    petition.PetitionSignatureChoices.ADDRESS_LINE_2 in petition.signature_fields
                    and form.instance.postal_address_line_2
                ):
                    body += f"\n{form.instance.postal_address_line_2}"

                last_line = ""
                if (
                    petition.PetitionSignatureChoices.CITY in petition.signature_fields
                    and form.instance.city
                ):
                    last_line += f"{form.instance.city}"
                if (
                    petition.PetitionSignatureChoices.STATE in petition.signature_fields
                    and form.instance.state
                ):
                    if form.instance.city:
                        last_line += ", "
                    last_line += form.instance.state
                if (
                    petition.PetitionSignatureChoices.ZIP_CODE in petition.signature_fields
                    and form.instance.zip_code
                ):
                    if form.instance.city or form.instance.state:
                        last_line += " "
                    last_line += form.instance.zip_code
                if last_line:
                    body += f"\n{last_line}"

                _link = "mailto:"
                _link += quote(", ".join(petition.email_to.splitlines()))
                _link += "?"
                params = {}
                if petition.email_cc:
                    params["cc"] = ", ".join(petition.email_cc.splitlines())
                params["subject"] = subject
                params["body"] = body
                _link += urlencode(params, quote_via=quote)

                response = HttpResponse(content="", status=303)
                response["Location"] = _link
                return response

            messages.add_message(request, messages.SUCCESS, message)

            if petition.redirect_after is not None:
                return redirect(
                    petition.redirect_after
                    + "?"
                    + urlencode(
                        {
                            k: v
                            for k, v in {
                                "first_name": form.instance.first_name,
                                "last_name": form.instance.last_name,
                                "address": form.instance.postal_address_line_1,
                            }.items()
                            if v is not None
                        }
                    )
                )

            if petition.campaign:
                return redirect("campaign", slug=petition.campaign.slug)
            else:
                return redirect("index")
    else:
        form = PetitionSignatureForm(petition=petition)

    return render(request, "petition/sign.html", context={"petition": petition, "form": form})
