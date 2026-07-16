import json
import os
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from emailblasts.forms import EmailDraftForm
from emailblasts.models import EmailBlast, EmailBlastImage, EmailBlastTarget, EmailBlastTargetNode
from emailblasts.targeting import (
    _email_blast_target_profiles,
    _email_draft_geojson_geometry,
    _email_draft_target_count,
    _email_draft_target_profiles,
    _target_primitive_nodes,
)
from emailblasts.tasks import send_email_blast
from emailblasts.utils import email_blast_full_body
from pbaabp.email import (
    EMAIL_IMAGE_PATH,
    render_email_html,
    send_email_message,
    template_from_string,
)
from profiles.models import Profile

_EMAIL_PREVIEW_CONTEXT = {
    "first_name": "Sam",
    "last_name": "Cyclist",
    "name": "Sam Cyclist",
    "email": "sam@example.com",
    "target_description": "match the selected audience",
}


def email_preview_context(**overrides):
    return {**_EMAIL_PREVIEW_CONTEXT, **overrides}


MUTABLE_EMAIL_BLAST_STATUSES = {
    EmailBlast.Status.DRAFT,
    EmailBlast.Status.SUBMITTED,
    EmailBlast.Status.REJECTED,
}


@login_required
@permission_required("profiles.can_organize", raise_exception=True)
def email_blast_list(request):
    show_all = request.GET.get("scope") == "all"
    blasts = (
        EmailBlast.objects.all() if show_all else EmailBlast.objects.filter(submitter=request.user)
    )

    return render(
        request,
        "emailblasts/email_blast_list.html",
        {
            "show_all": show_all,
            "draft_blasts": _email_blast_list_items(
                blasts.filter(status=EmailBlast.Status.DRAFT).order_by("-updated_at")
            ),
            "submitted_blasts": _email_blast_list_items(
                blasts.filter(
                    status__in=[
                        EmailBlast.Status.SUBMITTED,
                        EmailBlast.Status.APPROVED,
                        EmailBlast.Status.SENDING,
                    ]
                ).order_by("-updated_at")
            ),
            "sent_blasts": _email_blast_list_items(
                blasts.filter(status=EmailBlast.Status.SENT).order_by("-updated_at", "-created_at")
            ),
        },
    )


@login_required
@permission_required("profiles.can_organize", raise_exception=True)
def email_draft(request, draft_id=None):
    draft = get_object_or_404(EmailBlast, id=draft_id) if draft_id else None

    if draft and draft.submitter != request.user:
        if request.method == "POST":
            raise PermissionDenied
        return redirect("email_draft_review", draft_id=draft.id)

    if draft and draft.status not in MUTABLE_EMAIL_BLAST_STATUSES:
        if request.method == "POST":
            messages.error(request, "This email blast can no longer be edited.")
        return redirect("email_draft_review", draft_id=draft.id)

    if request.method == "POST":
        form = EmailDraftForm(request.POST)
        if form.is_valid():
            action = request.POST.get("action")
            if action == "send_example":
                try:
                    _send_email_blast_example(
                        subject=form.cleaned_data["subject"],
                        body=form.cleaned_data["body"],
                        target_description=form.cleaned_data["target_description"],
                        reply_to=form.cleaned_data["reply_to"],
                        user=request.user,
                    )
                    messages.success(request, f"Sent a test email to {request.user.email}.")
                except ValueError as error:
                    messages.error(request, str(error))
                target_rows = _email_draft_target_rows_from_post(request.POST)
                return _render_email_draft(
                    request,
                    form=form,
                    draft=draft,
                    target_rows=target_rows,
                )

            target_queryset, target_name, target_data = _email_draft_target(form)
            target = _email_blast_target_object(
                form.cleaned_data["target_name"],
                form.cleaned_data["target_description"],
                form.cleaned_data["target_operator"],
                target_data,
                request.user,
                existing_target=draft.target if draft else None,
            )
            status = (
                EmailBlast.Status.DRAFT if action == "save_draft" else EmailBlast.Status.SUBMITTED
            )
            draft = draft or EmailBlast(submitter=request.user)
            draft.subject = form.cleaned_data["subject"]
            draft.body = form.cleaned_data["body"]
            draft.reply_to = form.cleaned_data["reply_to"]
            draft.target = target
            draft.status = status
            draft.save()
            target_count = _email_draft_target_count(target_queryset)
            message = (
                "Draft email blast saved"
                if status == EmailBlast.Status.DRAFT
                else "Draft email blast submitted"
            )
            messages.success(
                request,
                f"{message} for {target_name} ({target_count} targeted profiles).",
            )
            if action == "save_draft":
                return redirect("email_draft_edit", draft_id=draft.id)
            return redirect("email_draft_review", draft_id=draft.id)
        target_rows = _email_draft_target_rows_from_post(request.POST)
    elif draft is not None:
        form = EmailDraftForm(initial=_email_draft_initial(draft))
        target_rows = _email_draft_initial_target_rows(draft)
    else:
        form = EmailDraftForm()
        target_rows = [{"target_type": "", "target_id": "", "target_geojson": ""}]

    return _render_email_draft(
        request,
        form=form,
        draft=draft,
        target_rows=target_rows,
    )


@login_required
@permission_required("profiles.can_organize", raise_exception=True)
def email_draft_review(request, draft_id):
    draft = get_object_or_404(EmailBlast, id=draft_id)
    is_author = request.user == draft.submitter
    is_mutable = draft.status in MUTABLE_EMAIL_BLAST_STATUSES

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "send_example" and (is_author or request.user.is_staff):
            try:
                _send_email_blast_example(
                    subject=draft.subject,
                    body=draft.body,
                    target_description=draft.target.description if draft.target else "",
                    reply_to=draft.reply_to,
                    user=request.user,
                )
                messages.success(request, f"Sent a test email to {request.user.email}.")
            except ValueError as error:
                messages.error(request, str(error))
        elif request.user.is_staff:
            if action == "approve" and draft.status == EmailBlast.Status.SUBMITTED:
                draft.status = EmailBlast.Status.APPROVED
                draft.save(update_fields=["status", "updated_at"])
                messages.success(request, "Email blast approved.")
            elif action == "reject" and draft.status in (
                EmailBlast.Status.SUBMITTED,
                EmailBlast.Status.APPROVED,
            ):
                draft.status = EmailBlast.Status.REJECTED
                draft.save(update_fields=["status", "updated_at"])
                messages.success(request, "Email blast rejected.")
            elif action == "send" and draft.status == EmailBlast.Status.APPROVED:
                transaction.on_commit(lambda: send_email_blast.delay(draft.id))
                messages.success(request, "Email blast queued to send.")
        return redirect("email_draft_review", draft_id=draft.id)

    return render(
        request,
        "emailblasts/email_draft_review.html",
        {
            "draft": draft,
            "is_author": is_author,
            "is_mutable": is_mutable,
            "is_staff": request.user.is_staff,
            **_draft_preview_context(draft),
        },
    )


def _draft_preview_context(draft):
    target_description = draft.target.description if draft.target else ""
    target_count = None
    target_name = ""
    target_geojson = ""
    if draft.target:
        target_count = _email_draft_target_count(_email_blast_target_profiles(draft.target))
        target_name = draft.target.name
        target_geojson = _email_draft_geojson_feature_collection(
            [
                {
                    "target_type": node.primitive_type,
                    "target_name": node.primitive_name,
                    "target_geojson": node.primitive_geojson,
                }
                for node in _target_primitive_nodes(draft.target)
            ]
        )
    return _build_preview_context(
        subject=draft.subject or "",
        body=draft.body,
        target_description=target_description,
        target_count=target_count,
        target_name=target_name,
        target_geojson=target_geojson,
    )


def _build_preview_context(
    *, subject, body, target_description, target_count, target_name, target_geojson
):
    prefix = getattr(settings, "EMAIL_SUBJECT_PREFIX", "")
    if prefix and subject:
        subject = f"{prefix} {subject}".strip()

    preview_html = ""
    preview_errors = []
    if body:
        full_body = email_blast_full_body(body, target_description)
        try:
            rendered = template_from_string(full_body).render(
                email_preview_context(target_description=target_description)
            )
            preview_html = render_email_html(rendered, for_preview=True)
        except Exception as error:
            preview_errors.append(f"Template error: {error}")

    return {
        "preview_subject": subject,
        "preview_html": preview_html,
        "target_count": target_count,
        "has_target_count": target_count is not None,
        "target_name": target_name,
        "target_geojson": target_geojson,
        "target_errors": preview_errors,
    }


def _render_email_draft(request, form, draft, target_rows):
    return render(
        request,
        "emailblasts/email_draft.html",
        {
            "form": form,
            "draft": draft,
            "preview_context": email_preview_context(),
            "target_choice_groups": form.target_choices,
            "target_rows": target_rows,
            "target_type_choices": form.target_type_choices(),
        },
    )


def _send_email_blast_example(subject, body, target_description, reply_to, user):
    if not user.email:
        raise ValueError("User does not have an email address.")

    full_body = email_blast_full_body(body, target_description)
    send_email_message(
        template_name=None,
        from_=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        context={
            "first_name": user.first_name,
            "last_name": user.last_name,
            "name": user.get_full_name(),
            "email": user.email,
            "target_description": target_description,
        },
        subject=f"[TEST] {subject}",
        message=full_body,
        reply_to=[reply_to],
    )


def _email_draft_initial(draft):
    initial = {
        "subject": draft.subject,
        "body": draft.body,
        "reply_to": draft.reply_to,
        "target_name": draft.target.name if draft.target else "",
        "target_description": draft.target.description if draft.target else "",
        "target_operator": _email_blast_target_root_operator(draft.target),
    }

    return initial


def _email_draft_initial_target_rows(draft):
    targets = _target_primitive_nodes(draft.target) if draft.target else []
    rows = []
    for target in targets:
        rows.append(
            {
                "target_type": target.primitive_type,
                "target_id": target.primitive_id,
                "target_geojson": json.dumps(target.primitive_geojson, indent=2)
                if target.primitive_geojson
                else "",
            }
        )

    return rows or [{"target_type": "", "target_id": "", "target_geojson": ""}]


def _email_draft_target_rows_from_post(post_data):
    rows = []
    indexes = set()
    for key in post_data.keys():
        match = re.match(r"target_type_(\d+)$", key)
        if match:
            indexes.add(int(match.group(1)))

    for index in sorted(indexes):
        rows.append(
            {
                "target_type": post_data.get(f"target_type_{index}", ""),
                "target_id": post_data.get(f"target_value_{index}", ""),
                "target_geojson": post_data.get(f"target_geojson_{index}", ""),
            }
        )

    return rows or [{"target_type": "", "target_id": "", "target_geojson": ""}]


@login_required
@permission_required("profiles.can_organize", raise_exception=True)
def email_draft_preview(request):
    target_queryset, target_name, target_errors, target_geojson = _email_draft_target_from_post(
        request.POST
    )
    target_count = (
        _email_draft_target_count(target_queryset) if target_queryset is not None else None
    )
    context = _build_preview_context(
        subject=request.POST.get("subject", ""),
        body=request.POST.get("body", ""),
        target_description=request.POST.get("target_description", ""),
        target_count=target_count,
        target_name=target_name,
        target_geojson=target_geojson,
    )
    context["target_errors"] = [*context["target_errors"], *target_errors]
    return render(request, "emailblasts/email_draft_preview.html", context)


@login_required
@permission_required("profiles.can_organize", raise_exception=True)
def email_draft_image(request, filename):
    allowed_files = {
        "header-img.png",
        "footer-img.png",
        "twitter-logo-24.png",
        "instagram-logo-24.png",
        "discord-logo-24.png",
    }
    if filename not in allowed_files:
        raise Http404()

    image_path = os.path.join(settings.BASE_DIR, EMAIL_IMAGE_PATH, filename)
    if not os.path.exists(image_path):
        raise Http404()

    return FileResponse(open(image_path, "rb"), content_type="image/png")


@login_required
@permission_required("profiles.can_organize", raise_exception=True)
def email_draft_upload_image(request):
    if request.method != "POST":
        raise Http404()

    image = request.FILES.get("image")
    if image is None:
        return JsonResponse({"error": "Choose an image to upload."}, status=400)

    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        return JsonResponse({"error": "Uploaded file must be an image."}, status=400)

    draft = None
    draft_id = request.POST.get("draft_id")
    if draft_id:
        draft = get_object_or_404(EmailBlast, id=draft_id)

    email_image = EmailBlastImage.objects.create(
        email_blast=draft,
        created_by=request.user,
        image=image,
        original_filename=image.name,
    )

    return JsonResponse(
        {
            "markdown": f"![{email_image.original_filename}]({email_image.email_src})",
            "src": email_image.email_src,
            "preview_url": email_image.image.url,
        }
    )


def _email_draft_target(form):
    target_data = _email_draft_target_data(form)
    target_operator = form.cleaned_data["target_operator"]
    return (
        _email_draft_profiles_for_targets(target_data, target_operator),
        _email_draft_target_name(target_data, target_operator),
        target_data,
    )


def _email_draft_target_from_post(post_data):
    form = EmailDraftForm(post_data)
    form.full_clean()
    target_errors = list(form.errors.get("__all__", []))
    if target_errors:
        return None, "", target_errors, ""

    try:
        target_queryset, target_name, target_data = _email_draft_target(form)
    except Exception:
        return None, "", ["Selected target was not found."], ""

    return (
        target_queryset,
        target_name,
        [],
        _email_draft_geojson_feature_collection(target_data),
    )


def _email_draft_target_data(form):
    return form.cleaned_data["target_rows"]


def _email_draft_target_name(target_data, operator=EmailBlastTargetNode.Operator.OR):
    if not target_data:
        return "No targets"
    if len(target_data) == 1:
        return target_data[0]["target_name"]
    target_names = [target["target_name"] for target in target_data]
    joiner = " AND " if operator == EmailBlastTargetNode.Operator.AND else " OR "
    summary = joiner.join(target_names[:3])
    if len(target_names) > 3:
        summary = f"{summary}{joiner}..."
    return summary[:255]


def _email_blast_target_object(
    name, description, target_operator, target_data, user, existing_target=None
):
    target = existing_target or EmailBlastTarget(created_by=user)
    target.name = name
    target.description = description
    target.save()
    target.nodes.all().delete()
    root = EmailBlastTargetNode.objects.create(
        target=target,
        operator=target_operator,
        position=0,
        created_by=user,
    )
    for position, primitive in enumerate(target_data):
        EmailBlastTargetNode.objects.create(
            target=target,
            parent=root,
            primitive_type=primitive["target_type"],
            primitive_id=primitive["target_id"],
            primitive_name=primitive["target_name"],
            primitive_geojson=primitive["target_geojson"],
            position=position,
            created_by=user,
        )
    return target


def _email_draft_profiles_for_targets(target_data, operator=EmailBlastTargetNode.Operator.OR):
    if not target_data:
        return Profile.objects.none()
    if any(
        target["target_type"] == EmailBlastTargetNode.TargetType.ALL_PROFILES
        for target in target_data
    ):
        return Profile.objects.all()

    profile_id_sets = []
    for target in target_data:
        profile_id_sets.append(
            set(_email_draft_target_profiles(target).values_list("pk", flat=True))
        )

    if not profile_id_sets:
        profile_ids = set()
    elif operator == EmailBlastTargetNode.Operator.AND:
        profile_ids = set.intersection(*profile_id_sets)
    else:
        profile_ids = set.union(*profile_id_sets)

    return Profile.objects.filter(pk__in=profile_ids)


def _email_blast_list_items(blasts):
    items = []
    for blast in blasts.select_related("target").prefetch_related("target__nodes"):
        blast.display_target_name = blast.target.name if blast.target else "No target"
        blast.display_target_count = (
            _email_draft_target_count(_email_blast_target_profiles(blast.target))
            if blast.target
            else 0
        )
        items.append(blast)
    return items


def _email_blast_target_root_operator(target):
    if target is None:
        return EmailBlastTargetNode.Operator.OR
    root = target.nodes.filter(parent__isnull=True).order_by("position", "id").first()
    return root.operator if root and root.operator else EmailBlastTargetNode.Operator.OR


def _email_draft_geojson_feature_collection(target_data):
    features = []
    for target in target_data:
        if target["target_type"] != EmailBlastTargetNode.TargetType.GEOJSON:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"name": target["target_name"]},
                "geometry": _email_draft_geojson_geometry(json.dumps(target["target_geojson"])),
            }
        )

    if not features:
        return ""
    return json.dumps({"type": "FeatureCollection", "features": features})
