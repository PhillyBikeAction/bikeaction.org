from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from projects.forms import ProjectApplicationForm
from projects.models import ProjectApplication


@login_required
def project_application_view(request, pk=None):
    profile_complete = request.user.profile.complete
    apps_connected = request.user.profile.apps_connected

    if not profile_complete:
        message = (
            "Your profile must be complete and "
            "you must connect your discord account "
            "to submit a project application."
        )
        messages.add_message(request, messages.ERROR, message)
        return redirect("profile")

    if not apps_connected:
        message = "You must connect your discord account " "to submit a project application."
        messages.add_message(request, messages.ERROR, message)
        return redirect("profile")

    if not request.user.profile.pronouns:
        message = (
            "You must set the pronouns field in your profile to submit a project application."
        )
        messages.add_message(request, messages.ERROR, message)
        return redirect("profile")

    application = get_object_or_404(ProjectApplication, id=pk)

    return render(request, "project_application_view.html", {"application": application})


@login_required
def project_application(request, pk=None):
    profile_complete = request.user.profile.complete
    apps_connected = request.user.profile.apps_connected

    if not profile_complete:
        message = (
            "Your profile must be complete and "
            "you must connect your discord account "
            "to submit a project application."
        )
        messages.add_message(request, messages.ERROR, message)
        return redirect("profile")

    if not apps_connected:
        message = "You must connect your discord account " "to submit a project application."
        messages.add_message(request, messages.ERROR, message)
        return redirect("profile")

    if not request.user.profile.pronouns:
        message = (
            "You must set the pronouns field in your profile to submit a project application."
        )
        messages.add_message(request, messages.ERROR, message)
        return redirect("profile")

    if pk:
        application = get_object_or_404(ProjectApplication, id=pk)
        if not application.draft:
            return redirect("project_application_view", pk=application.id)

    if request.method == "POST" and "save-draft" in request.POST:
        form = ProjectApplicationForm(request.POST, label_suffix="")
        if pk:
            application = get_object_or_404(ProjectApplication, id=pk)
        else:
            application = ProjectApplication(submitter=request.user, draft=True)
        application.data = form.to_json()
        application.save()
        messages.add_message(request, messages.SUCCESS, "Application saved, but not submitted")
        return redirect("profile")

    elif request.method == "POST" and "submit-application" in request.POST:
        form = ProjectApplicationForm(request.POST, label_suffix="")
        if form.is_valid():
            submission = ProjectApplication(submitter=request.user, draft=False)
            submission.data = form.to_json()
            submission.render_markdown()
            submission.save()
            if pk:
                application = ProjectApplication.objects.filter(id=pk)
                if application:
                    application.delete()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Application submitted! You'll hear from organizers soon.",
            )
            return redirect("profile")

    else:
        if pk:
            application = get_object_or_404(ProjectApplication, id=pk)
            form = ProjectApplicationForm(
                initial={k: v["value"] for k, v in application.data.items()}, label_suffix=""
            )
        else:
            form = ProjectApplicationForm(label_suffix="")

    return render(request, "project_application_form.html", {"form": form})
