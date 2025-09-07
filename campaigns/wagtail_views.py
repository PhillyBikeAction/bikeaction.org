"""
Views for handling Wagtail campaign petition submissions.
These work alongside the Wagtail page models to process form data.
"""

from urllib.parse import quote, urlencode

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from campaigns.models import Petition, PetitionSignature


def get_petition_from_wagtail_block(campaign_page, petition_id):
    """
    Extract petition from a CampaignPage's StreamField.
    Returns the petition instance or None if not found.
    """
    for block in campaign_page.body:
        if block.block_type == "petition":
            block_value = block.value
            petition = block_value.get("petition")
            # Check if this is the petition we're looking for
            if petition and str(petition.id) == str(petition_id):
                return petition
    return None


def get_or_create_petition_model(petition_block_data):
    """
    Get existing Petition model or create a new one from block data.
    This maintains backward compatibility with existing petition signatures.
    """
    # Check if using an existing petition
    if petition_block_data.get("use_existing_petition") and petition_block_data.get(
        "existing_petition_id"
    ):
        petition_id = petition_block_data.get("existing_petition_id")
    else:
        petition_id = petition_block_data.get("petition_id")

    if petition_id:
        try:
            # Try to find existing petition
            petition = Petition.objects.get(id=petition_id)
            return petition
        except (Petition.DoesNotExist, ValueError):
            pass

    # Create a new Petition model from block data
    petition = Petition(
        title=petition_block_data.get("title"),
        letter=petition_block_data.get("letter"),
        call_to_action=petition_block_data.get("call_to_action"),
        call_to_action_header=petition_block_data.get("call_to_action_header", True),
        display_on_campaign_page=petition_block_data.get("display_on_campaign_page", True),
        signature_goal=petition_block_data.get("signature_goal"),
        show_submissions=petition_block_data.get("show_submissions", True),
    )

    # Email settings
    email_settings = petition_block_data.get("email_settings", {})
    petition.send_email = email_settings.get("send_email", False)
    petition.mailto_send = email_settings.get("mailto_send", False)
    petition.email_subject = email_settings.get("email_subject")
    petition.email_body = email_settings.get("email_body")
    petition.email_to = email_settings.get("email_to")
    petition.email_cc = email_settings.get("email_cc")
    petition.email_include_comment = email_settings.get("email_include_comment", False)

    # Other settings
    petition.create_account_opt_in = petition_block_data.get("create_account_opt_in", False)
    petition.redirect_after = petition_block_data.get("redirect_after")

    # Signature fields
    signature_fields = petition_block_data.get("signature_fields", {})
    petition.signature_fields = signature_fields.get("enabled_fields", [])

    petition.save()
    return petition


@require_http_methods(["POST"])
def sign_petition_wagtail(request, campaign_page, petition_id):
    """
    Handle petition signature submission from Wagtail campaign pages.
    """
    # Get petition from StreamField
    petition = get_petition_from_wagtail_block(campaign_page, petition_id)
    if not petition:
        raise Http404("Petition not found")

    # Create signature
    signature = PetitionSignature()
    signature.petition = petition

    # Process form fields from the petition's form
    form = petition.form(request.POST)

    if not form.is_valid():
        messages.error(request, "Please correct the errors below.")
        return redirect(campaign_page.url)

    # Copy form data to signature
    for field_name, value in form.cleaned_data.items():
        if hasattr(signature, field_name):
            setattr(signature, field_name, value)

    # Handle opt-ins
    signature.newsletter_opt_in = request.POST.get("newsletter_opt_in") == "on"
    signature.create_account_opt_in = request.POST.get("create_account_opt_in") == "on"

    # Check for existing signature
    existing_signature = None
    if signature.email:
        existing_signature = PetitionSignature.objects.filter(
            petition=petition, email__iexact=signature.email
        ).first()

    # Save signature
    signature.save()

    # Handle email sending
    send_email = request.POST.get("send_email") == "on"

    if petition.send_email and send_email and not existing_signature:
        # Prepare email body
        email_body = ""
        if petition.email_body:
            email_body += petition.email_body + "\n\n"

        if petition.email_include_comment and signature.comment:
            email_body += signature.comment + "\n\n"

        email_body += f"- {signature.first_name} {signature.last_name}"

        # Add address info if available
        if signature.phone_number:
            email_body += f"\n{signature.phone_number}"

        if signature.postal_address_line_1:
            email_body += f"\n{signature.postal_address_line_1}"
        if signature.postal_address_line_2:
            email_body += f"\n{signature.postal_address_line_2}"

        last_line = ""
        if signature.city:
            last_line += signature.city
        if signature.state:
            if signature.city:
                last_line += ", "
            last_line += signature.state
        if signature.zip_code:
            if signature.city or signature.state:
                last_line += " "
            last_line += signature.zip_code
        if last_line:
            email_body += f"\n{last_line}"

        # Send email
        try:
            email = EmailMessage(
                subject=petition.email_subject or "Petition Signature",
                body=email_body,
                from_email=(
                    f"{signature.first_name} {signature.last_name} "
                    f"<{settings.DEFAULT_FROM_EMAIL}>"
                ),
                to=petition.email_to.splitlines() if petition.email_to else [],
                cc=(petition.email_cc.splitlines() if petition.email_cc else []),
                reply_to=[signature.email] if signature.email else [],
            )
            email.send()
            messages.success(request, "Signature captured! Email sent!")
        except Exception as e:
            messages.warning(request, f"Signature captured, but email failed: {e}")

    elif petition.mailto_send:
        # Handle mailto link
        subject = petition.email_subject or "Petition Signature"
        body = email_body

        _link = "mailto:"
        _link += quote(", ".join(petition.email_to.splitlines() if petition.email_to else []))
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
    else:
        messages.success(request, "Signature captured!")

    # Handle redirect
    if petition.redirect_after:
        return redirect(petition.redirect_after)

    # Redirect back to campaign page
    return redirect(campaign_page.url)


def petition_signatures_wagtail(request, campaign_page, petition_id):
    """
    Return petition signatures for HTMX updates.
    """
    # Get petition from StreamField
    petition = get_petition_from_wagtail_block(campaign_page, petition_id)
    if not petition:
        raise Http404("Petition not found")

    # Get signatures
    signatures = petition.signatures.filter(visible=True).order_by("-created_at")[:10]

    # Return partial template
    return render(
        request,
        "campaigns/_partial_signatures.html",
        {
            "petition": petition,
            "signatures": signatures,
        },
    )
