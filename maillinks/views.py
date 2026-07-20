import qrcode
import qrcode.image.svg
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from maillinks.models import MailLink


def get_accessible_maillink_or_404(request, slug):
    maillink_object = MailLink.objects.filter(slug=slug).first()
    if maillink_object is None:
        raise Http404
    if maillink_object.active:
        return maillink_object
    if (
        request.user.is_authenticated
        and hasattr(request.user, "profile")
        and request.user.profile.is_organizer
    ):
        return maillink_object
    raise Http404


def maillink(request, slug):
    maillink_object = get_accessible_maillink_or_404(request, slug)

    response = HttpResponse(content="", status=303)
    response["Location"] = maillink_object.link(
        first_name=request.GET.get("first_name"),
        last_name=request.GET.get("last_name"),
        address=request.GET.get("address"),
    )

    return response


def view(request, slug):
    maillink_object = get_accessible_maillink_or_404(request, slug)

    data = {
        "first_name": request.GET.get("first_name"),
        "last_name": request.GET.get("last_name"),
        "address": request.GET.get("address"),
    }

    return render(
        request,
        "maillink.html",
        context={
            "maillink": maillink_object,
            "mail_link": maillink_object.link(
                first_name=request.GET.get("first_name"),
                last_name=request.GET.get("last_name"),
                address=request.GET.get("address"),
            ),
            **data,
        },
    )


def flyer(request, slug):
    maillink_object = get_accessible_maillink_or_404(request, slug)

    qrlink = request.build_absolute_uri(reverse("maillink_send", kwargs={"slug": slug}))
    qrcode_img = qrcode.make(qrlink, image_factory=qrcode.image.svg.SvgPathImage)

    return render(
        request,
        "flyer.html",
        context={"maillink": maillink_object, "qrcode": qrcode_img.to_string(encoding="unicode")},
    )
