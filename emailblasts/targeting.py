import json

from django.contrib.gis.geos import GEOSGeometry
from django.db.models.functions import Lower

from campaigns.models import PetitionSignature
from emailblasts.forms import EmailDraftForm
from emailblasts.models import EmailBlastTargetNode
from events.models import EventSignIn
from profiles.models import Profile


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


def _email_draft_target_count(queryset):
    return queryset.exclude(user__email="").values("user__email").distinct().count()
