from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from community_fund.forms import CommunityActionFundApplicationForm
from community_fund.models import (
    CommunityActionFundApplication,
    CommunityActionFundApplicationPeriod,
    CommunityActionFundSupportingMaterial,
)


def applications_are_open():
    return CommunityActionFundApplicationPeriod.applications_are_open()


@login_required
def application(request, pk=None):
    if not applications_are_open():
        messages.error(request, "Community Action Fund applications are currently closed.")
        return redirect("profile")

    if pk:
        application = get_object_or_404(
            CommunityActionFundApplication, id=pk, submitter=request.user
        )
        if not application.draft:
            return redirect("community_action_fund_application_view", pk=application.id)

    if request.method == "POST" and "save-draft" in request.POST:
        form = CommunityActionFundApplicationForm(request.POST, request.FILES, label_suffix="")
        application = (
            get_object_or_404(
                CommunityActionFundApplication, id=pk, submitter=request.user, draft=True
            )
            if pk
            else CommunityActionFundApplication(submitter=request.user, draft=True)
        )
        application.data = form.to_json()
        application.render_markdown()
        application.save()
        CommunityActionFundSupportingMaterial.objects.bulk_create(
            [
                CommunityActionFundSupportingMaterial(application=application, file=file)
                for file in form.files.getlist("supporting_materials")
            ]
        )
        application.render_markdown()
        CommunityActionFundApplication.objects.filter(id=application.id).update(
            markdown=application.markdown
        )
        messages.success(request, "Application saved, but not submitted.")
        return redirect("profile")

    if request.method == "POST" and "submit-application" in request.POST:
        form = CommunityActionFundApplicationForm(request.POST, request.FILES, label_suffix="")
        if form.is_valid():
            with transaction.atomic():
                submission = CommunityActionFundApplication(submitter=request.user, draft=False)
                submission.data = form.to_json()
                submission.render_markdown()
                submission.save()
                CommunityActionFundSupportingMaterial.objects.bulk_create(
                    [
                        CommunityActionFundSupportingMaterial(application=submission, file=file)
                        for file in form.cleaned_data["supporting_materials"]
                    ]
                )
                if pk:
                    CommunityActionFundSupportingMaterial.objects.filter(application_id=pk).update(
                        application=submission
                    )
                submission.render_markdown()
                CommunityActionFundApplication.objects.filter(id=submission.id).update(
                    markdown=submission.markdown
                )
                if pk:
                    CommunityActionFundApplication.objects.filter(
                        id=pk, submitter=request.user, draft=True
                    ).delete()
            messages.success(request, "Application submitted! You'll hear from us soon.")
            return redirect("profile")
    elif pk:
        application = get_object_or_404(
            CommunityActionFundApplication, id=pk, submitter=request.user, draft=True
        )
        form = CommunityActionFundApplicationForm(
            initial={
                **{key: value["value"] for key, value in application.data.items()},
            },
            label_suffix="",
        )
    else:
        form = CommunityActionFundApplicationForm(
            initial={
                "primary_contact_name": request.user.get_full_name(),
                "email": request.user.email,
            },
            label_suffix="",
        )

    return render(
        request,
        "community_fund/application_form.html",
        {
            "form": form,
            "existing_materials": application.supporting_materials.all() if pk else [],
        },
    )


@login_required
def application_view(request, pk):
    application = get_object_or_404(
        CommunityActionFundApplication, id=pk, submitter=request.user, draft=False
    )
    return render(request, "community_fund/application_view.html", {"application": application})


@login_required
@require_POST
def application_delete(request, pk):
    application = get_object_or_404(
        CommunityActionFundApplication, id=pk, submitter=request.user, draft=True
    )
    application.delete()
    messages.success(request, "Community Action Fund application draft deleted.")
    return redirect("profile")
