import re

from django import template
from django.http import Http404
from django.urls import Resolver404, resolve
from django.utils.translation import gettext_lazy as _
from wagtail.models import Page, Site
from wagtail.views import serve as wagtail_serve

register = template.Library()


@register.simple_tag(takes_context=True)
def clean_url(context, path):
    request = context["request"]
    return request.build_absolute_uri(path)


@register.filter(name="splitlines")
def splitlines_filter(value):
    return value.splitlines()


def _slug_label(slug):
    return re.sub(r"[-_]+", " ", slug).title()


def _crumb(request, root_page, components):
    """Resolve one URL prefix to a (label, url) pair. url is None when
    nothing is served at that prefix, so the crumb renders unlinked."""
    prefix = "/" + "/".join(components) + "/"
    label = _slug_label(components[-1])

    try:
        match = resolve(prefix)
    except Resolver404:
        return label, None

    if match.func is not wagtail_serve:
        return label, prefix

    if root_page is None:
        return label, None
    try:
        result = root_page.specific.route(request, components)
    except Http404:
        return label, None
    if result.page.url_path == root_page.url_path + "/".join(components) + "/":
        label = result.page.title
    return label, prefix


@register.inclusion_tag("templatetags/breadcrumbs.html", takes_context=True)
def breadcrumbs(context):
    request = context["request"]
    components = [c for c in request.path.split("/") if c]
    if not components:
        return {"crumbs": []}

    site = Site.find_for_request(request)
    root_page = site.root_page if site else None

    crumbs = [{"label": _("Home"), "url": "/"}]
    for depth in range(1, len(components) + 1):
        label, url = _crumb(request, root_page, components[:depth])
        crumbs.append({"label": label, "url": url})

    current = context.get("page")
    if isinstance(current, Page):
        crumbs[-1]["label"] = current.title
    crumbs[-1]["url"] = None

    return {"crumbs": crumbs}
