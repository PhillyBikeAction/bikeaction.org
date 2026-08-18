import json
from dataclasses import dataclass

from django.contrib.gis.geos import GEOSGeometry
from django.db.models.functions import Lower
from django.db.models.functions import Trim

from campaigns.models import PetitionSignature
from emailblasts.forms import EmailDraftForm
from emailblasts.models import EmailBlastTargetNode
from events.models import EventRSVP, EventSignIn
from profiles.models import DoNotEmail, Profile


@dataclass
class EmailBlastRecipient:
    email: str
    first_name: str = ""
    last_name: str = ""
    profile: Profile | None = None

    @property
    def name(self):
        return " ".join(part for part in [self.first_name, self.last_name] if part)


def _normalize_email(email):
    return (email or "").strip().lower()


def _email_draft_geojson_geometry(geojson):
    data = json.loads(geojson)
    return EmailDraftForm().geojson_geometry(data)


def _email_draft_geojson_profiles(geojson):
    geometry = _email_draft_geojson_geometry(geojson)
    geom = GEOSGeometry(json.dumps(geometry))
    geom.srid = 4326
    return Profile.objects.filter(location__within=geom)


def _email_draft_target_profiles(target):
    if target["target_type"] == EmailBlastTargetNode.TargetType.ALL_PROFILES:
        return Profile.objects.all()
    if target["target_type"] == EmailBlastTargetNode.TargetType.VOLUNTEERS:
        return Profile.objects.filter(volunteer_opt_in=True)
    if target["target_type"] == EmailBlastTargetNode.TargetType.GEOJSON:
        return _email_draft_geojson_profiles(json.dumps(target["target_geojson"]))
    if target["target_type"] == EmailBlastTargetNode.TargetType.PETITION:
        signer_emails = (
            PetitionSignature.objects.filter(petition_id=target["target_id"])
            .exclude(email__isnull=True)
            .exclude(email="")
            .annotate(email_lower=Lower("email"))
            .values_list("email_lower", flat=True)
        )
        return Profile.objects.annotate(user_email_lower=Lower("user__email")).filter(
            user_email_lower__in=signer_emails
        )
    if target["target_type"] == EmailBlastTargetNode.TargetType.EVENT_SIGNIN:
        sign_in_emails = (
            EventSignIn.objects.filter(event_id=target["target_id"])
            .exclude(email__isnull=True)
            .exclude(email="")
            .annotate(email_lower=Lower("email"))
            .values_list("email_lower", flat=True)
        )
        return Profile.objects.annotate(user_email_lower=Lower("user__email")).filter(
            user_email_lower__in=sign_in_emails
        )
    if target["target_type"] == EmailBlastTargetNode.TargetType.EVENT_RSVP:
        rsvp_emails = (
            EventRSVP.objects.filter(event_id=target["target_id"])
            .exclude(email__isnull=True)
            .exclude(email="")
            .annotate(email_lower=Lower("email"))
            .values_list("email_lower", flat=True)
        )
        rsvp_user_emails = (
            EventRSVP.objects.filter(event_id=target["target_id"], user__isnull=False)
            .exclude(user__email__isnull=True)
            .exclude(user__email="")
            .annotate(email_lower=Lower("user__email"))
            .values_list("email_lower", flat=True)
        )
        return Profile.objects.annotate(user_email_lower=Lower("user__email")).filter(
            user_email_lower__in=[*rsvp_emails, *rsvp_user_emails]
        )
    if target["target_type"] == EmailBlastTargetNode.TargetType.LEGACY:
        return Profile.objects.none()

    field_name = EmailDraftForm.TARGET_FIELD_BY_TYPE.get(target["target_type"])
    model = EmailDraftForm.MODEL_BY_TARGET_FIELD[field_name]
    return model.objects.get(pk=target["target_id"]).contained_profiles.all()


def _target_data_from_node(node):
    return {
        "target_type": node.primitive_type,
        "target_id": node.primitive_id,
        "target_name": node.primitive_name,
        "target_geojson": node.primitive_geojson,
    }


def _profile_recipient_map(queryset):
    recipients = {}
    profiles = (
        queryset.select_related("user")
        .exclude(user__email__isnull=True)
        .annotate(email_key=Lower(Trim("user__email")))
        .exclude(email_key="")
        .order_by("email_key", "pk")
    )
    for profile in profiles:
        recipients.setdefault(
            profile.email_key,
            EmailBlastRecipient(
                email=profile.email_key,
                first_name=profile.user.first_name,
                last_name=profile.user.last_name,
                profile=profile,
            ),
        )
    return recipients


def _profiles_by_email(emails):
    return {
        profile.email_key: profile
        for profile in Profile.objects.select_related("user")
        .annotate(email_key=Lower(Trim("user__email")))
        .filter(email_key__in=emails)
        .order_by("email_key", "pk")
    }


def _petition_signature_recipient_map(petition_id):
    signatures = (
        PetitionSignature.objects.filter(petition_id=petition_id)
        .exclude(email__isnull=True)
        .annotate(email_key=Lower(Trim("email")))
        .exclude(email_key="")
        .order_by("email_key", "created_at", "pk")
    )
    profiles = _profiles_by_email({signature.email_key for signature in signatures})
    recipients = {}
    for signature in signatures:
        profile = profiles.get(signature.email_key)
        recipients.setdefault(
            signature.email_key,
            EmailBlastRecipient(
                email=signature.email_key,
                first_name=signature.first_name or (profile.user.first_name if profile else ""),
                last_name=signature.last_name or (profile.user.last_name if profile else ""),
                profile=profile,
            ),
        )
    return recipients


def _event_signin_recipient_map(event_id):
    signins = (
        EventSignIn.objects.filter(event_id=event_id)
        .exclude(email__isnull=True)
        .annotate(email_key=Lower(Trim("email")))
        .exclude(email_key="")
        .order_by("email_key", "created_at", "pk")
    )
    profiles = _profiles_by_email({signin.email_key for signin in signins})
    recipients = {}
    for signin in signins:
        profile = profiles.get(signin.email_key)
        recipients.setdefault(
            signin.email_key,
            EmailBlastRecipient(
                email=signin.email_key,
                first_name=signin.first_name or (profile.user.first_name if profile else ""),
                last_name=signin.last_name or (profile.user.last_name if profile else ""),
                profile=profile,
            ),
        )
    return recipients


def _event_rsvp_recipient_map(event_id):
    rsvps = EventRSVP.objects.filter(event_id=event_id).select_related("user").order_by("pk")
    email_keys = {
        _normalize_email(rsvp.email or (rsvp.user.email if rsvp.user else "")) for rsvp in rsvps
    }
    profiles = _profiles_by_email({email for email in email_keys if email})
    recipients = {}
    for rsvp in rsvps:
        email_key = _normalize_email(rsvp.email or (rsvp.user.email if rsvp.user else ""))
        if not email_key:
            continue
        profile = profiles.get(email_key)
        recipients.setdefault(
            email_key,
            EmailBlastRecipient(
                email=email_key,
                first_name=rsvp.first_name or (rsvp.user.first_name if rsvp.user else ""),
                last_name=rsvp.last_name or (rsvp.user.last_name if rsvp.user else ""),
                profile=profile,
            ),
        )
    return recipients


def _email_blast_target_recipient_map_for_node(node):
    if node.operator:
        child_maps = [
            _email_blast_target_recipient_map_for_node(child)
            for child in node.children.order_by("position", "id")
        ]
        if not child_maps:
            return {}
        if node.operator == EmailBlastTargetNode.Operator.AND:
            email_keys = set.intersection(*(set(child_map.keys()) for child_map in child_maps))
            return {
                email_key: next(
                    child_map[email_key] for child_map in child_maps if email_key in child_map
                )
                for email_key in email_keys
            }

        recipients = {}
        for child_map in child_maps:
            for email_key, recipient in child_map.items():
                recipients.setdefault(email_key, recipient)
        return recipients

    target_data = _target_data_from_node(node)
    if node.primitive_type == EmailBlastTargetNode.TargetType.PETITION:
        return _petition_signature_recipient_map(node.primitive_id)
    if node.primitive_type == EmailBlastTargetNode.TargetType.EVENT_SIGNIN:
        return _event_signin_recipient_map(node.primitive_id)
    if node.primitive_type == EmailBlastTargetNode.TargetType.EVENT_RSVP:
        return _event_rsvp_recipient_map(node.primitive_id)
    return _profile_recipient_map(_email_draft_target_profiles(target_data))


def _email_draft_target_recipient_map(target_data):
    if target_data["target_type"] == EmailBlastTargetNode.TargetType.PETITION:
        return _petition_signature_recipient_map(target_data["target_id"])
    if target_data["target_type"] == EmailBlastTargetNode.TargetType.EVENT_SIGNIN:
        return _event_signin_recipient_map(target_data["target_id"])
    if target_data["target_type"] == EmailBlastTargetNode.TargetType.EVENT_RSVP:
        return _event_rsvp_recipient_map(target_data["target_id"])
    return _profile_recipient_map(_email_draft_target_profiles(target_data))


def _combine_recipient_maps(recipient_maps, operator):
    if not recipient_maps:
        return {}
    if operator == EmailBlastTargetNode.Operator.AND:
        email_keys = set.intersection(
            *(set(recipient_map.keys()) for recipient_map in recipient_maps)
        )
        return {
            email_key: next(
                recipient_map[email_key]
                for recipient_map in recipient_maps
                if email_key in recipient_map
            )
            for email_key in email_keys
        }

    recipients = {}
    for recipient_map in recipient_maps:
        for email_key, recipient in recipient_map.items():
            recipients.setdefault(email_key, recipient)
    return recipients


def _filter_suppressed_recipients(recipients):
    suppressed_emails = set(
        DoNotEmail.objects.annotate(email_key=Lower(Trim("email")))
        .exclude(email_key="")
        .values_list("email_key", flat=True)
    )
    return {
        email: recipient
        for email, recipient in recipients.items()
        if email not in suppressed_emails
    }


def _email_draft_target_recipients_for_targets(
    target_data, operator=EmailBlastTargetNode.Operator.OR, *, exclude_suppressed=True
):
    if not target_data:
        return []
    if any(
        target["target_type"] == EmailBlastTargetNode.TargetType.ALL_PROFILES
        for target in target_data
    ):
        recipients = _profile_recipient_map(Profile.objects.all())
    else:
        recipients = _combine_recipient_maps(
            [_email_draft_target_recipient_map(target) for target in target_data],
            operator,
        )
    if exclude_suppressed:
        recipients = _filter_suppressed_recipients(recipients)
    return [recipients[email] for email in sorted(recipients)]


def _email_draft_target_recipient_count(target_data, operator=EmailBlastTargetNode.Operator.OR):
    return len(_email_draft_target_recipients_for_targets(target_data, operator))


def _email_blast_target_recipients(target, *, exclude_suppressed=True):
    root = target.nodes.filter(parent__isnull=True).order_by("position", "id").first()
    if root is None:
        return []
    recipients = _email_blast_target_recipient_map_for_node(root)
    if exclude_suppressed:
        recipients = _filter_suppressed_recipients(recipients)
    return [recipients[email] for email in sorted(recipients)]


def _email_blast_target_node_profile_ids(node):
    if node.operator:
        child_sets = [
            _email_blast_target_node_profile_ids(child)
            for child in node.children.order_by("position", "id")
        ]
        if not child_sets:
            return set()
        if node.operator == EmailBlastTargetNode.Operator.AND:
            return set.intersection(*child_sets)
        return set.union(*child_sets)

    return set(
        _email_draft_target_profiles(_target_data_from_node(node)).values_list("pk", flat=True)
    )


def _target_primitive_nodes(target):
    if target is None:
        return []
    root = target.nodes.filter(parent__isnull=True).order_by("position", "id").first()
    if root and root.operator:
        return list(root.children.order_by("position", "id"))
    return list(target.nodes.filter(operator="").order_by("position", "id"))


def _email_blast_target_profiles(target):
    root = target.nodes.filter(parent__isnull=True).order_by("position", "id").first()
    if root is None:
        return Profile.objects.none()
    profile_ids = _email_blast_target_node_profile_ids(root)
    return Profile.objects.filter(pk__in=profile_ids)


def _email_blast_recipient_profiles(queryset, *, exclude_suppressed=True):
    suppressed_emails = set()
    if exclude_suppressed:
        suppressed_emails = set(
            DoNotEmail.objects.annotate(email_key=Lower(Trim("email")))
            .exclude(email_key="")
            .values_list("email_key", flat=True)
        )
    seen_emails = set()
    recipients = []

    profiles = (
        queryset.select_related("user")
        .exclude(user__email__isnull=True)
        .annotate(email_key=Lower(Trim("user__email")))
        .exclude(email_key="")
        .order_by("email_key", "pk")
    )
    for profile in profiles:
        if profile.email_key in seen_emails:
            continue
        seen_emails.add(profile.email_key)
        if exclude_suppressed and profile.email_key in suppressed_emails:
            continue
        recipients.append(profile)

    return recipients


def _email_draft_target_count(queryset):
    return len(_email_blast_recipient_profiles(queryset))


def _email_blast_target_recipient_count(target):
    return len(_email_blast_target_recipients(target))
