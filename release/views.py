import uuid

from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render

from pbaabp.tasks import subscribe_to_newsletter
from release.forms import ReleaseSignatureForm
from release.models import Release


def _fetch_release_by_slug_or_id(release_slug_or_id):
    try:
        uuid.UUID(release_slug_or_id)
        release_by_id = Release.objects.filter(id=release_slug_or_id).first()
    except ValueError:
        release_by_id = None
    release_by_slug = Release.objects.filter(slug=release_slug_or_id).first()

    if release_by_id is not None:
        return release_by_id
    elif release_by_slug is not None:
        return release_by_slug
    else:
        return None


def release_view(request, release_slug_or_id):
    release = _fetch_release_by_slug_or_id(release_slug_or_id)
    if release is None:
        raise Http404
    html = "<html><body>%s</body></html>" % str(release)
    return HttpResponse(html)


def release_signature(request, release_slug_or_id):
    release = _fetch_release_by_slug_or_id(release_slug_or_id)
    if release is None:
        raise Http404
    if request.method == "POST":
        form = ReleaseSignatureForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["newsletter_opt_in"]:
                transaction.on_commit(
                    lambda: subscribe_to_newsletter.delay(
                        form.instance.email,
                        form.instance.nickname,
                        tags=["release-signature", f"release-{release.slug}"],
                    )
                )

            form.instance.release = release
            form.save()

            if request.GET.get("kiosk", False):
                return redirect("release_signature_kiosk_postroll", release_slug_or_id=release.slug)
            else:
                return HttpResponseRedirect("https://bikeaction.org")
    else:
        form = ReleaseSignatureForm()

    return render(request, "signature.html", context={"release": release, "form": form})


def release_signature_kiosk_postroll(request, release_slug_or_id):
    release = _fetch_release_by_slug_or_id(release_slug_or_id)
    if release is None:
        raise Http404
    return render(request, "signature-kiosk-postroll.html", context={"release": release})
