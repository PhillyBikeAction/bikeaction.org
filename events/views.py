import datetime
import re
import uuid
from urllib.parse import quote_plus

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView

from events.forms import EventRSVPForm, EventSignInForm
from events.models import EventRSVP, EventSignIn, ScheduledEvent
from events.signin_cookie import (
    EVENT_SIGNIN_COOKIE_NAME,
    EVENT_SIGNIN_COOKIE_TYPE_SIGNIN,
    EVENT_SIGNIN_COOKIE_TYPE_USER,
    decrypt_event_signin_payload,
    set_event_signin_cookie,
)


def _fetch_event_by_slug_or_id(event_slug_or_id):
    try:
        uuid.UUID(event_slug_or_id)
        event_by_id = ScheduledEvent.objects.filter(id=event_slug_or_id).first()
    except ValueError:
        event_by_id = None
    event_by_slug = ScheduledEvent.objects.filter(slug=event_slug_or_id).first()

    if event_by_id is not None:
        return event_by_id
    elif event_by_slug is not None:
        return event_by_slug
    else:
        return None


def _event_signin_data_from_signin(signin):
    return {
        "first_name": signin.first_name,
        "last_name": signin.last_name,
        "email": signin.email,
        "zip_code": signin.zip_code,
        "newsletter_opt_in": signin.newsletter_opt_in,
    }


def _event_signin_district_from_profile(profile):
    district = profile.district
    if district is None:
        return None

    match = re.search(r"\d+", district.name)
    if match is None:
        return None

    district_number = int(match.group())
    if district_number in EventSignIn.District.values:
        return district_number
    return None


def _event_signin_data_from_user(user):
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        profile = None

    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "zip_code": profile.zip_code if profile is not None else "",
        "newsletter_opt_in": profile.newsletter_opt_in if profile is not None else False,
    }


def _event_signin_data_is_complete(signin_data):
    return all(
        [
            signin_data.get("first_name"),
            signin_data.get("last_name"),
            signin_data.get("email"),
        ]
    )


def _remembered_signin_identity(identity_type, source, first_name, signin_data):
    return {
        "type": identity_type,
        "source": source,
        "first_name": first_name,
        "data": signin_data,
        "complete": _event_signin_data_is_complete(signin_data),
    }


def _remembered_signin_identity_from_cookie(request):
    payload = decrypt_event_signin_payload(request.COOKIES.get(EVENT_SIGNIN_COOKIE_NAME))
    if payload is None:
        return None

    if payload.get("type") == EVENT_SIGNIN_COOKIE_TYPE_USER:
        user = User.objects.filter(id=payload.get("id")).first()
        if user is None or not user.email:
            return None
        return _remembered_signin_identity(
            EVENT_SIGNIN_COOKIE_TYPE_USER,
            user,
            user.first_name,
            _event_signin_data_from_user(user),
        )

    if payload.get("type") == EVENT_SIGNIN_COOKIE_TYPE_SIGNIN:
        signin = EventSignIn.objects.filter(id=payload.get("id")).first()
        if signin is None:
            return None
        return _remembered_signin_identity(
            EVENT_SIGNIN_COOKIE_TYPE_SIGNIN,
            signin,
            signin.first_name,
            _event_signin_data_from_signin(signin),
        )

    return None


def _event_signin_identity(request):
    if request.user.is_authenticated and request.user.email:
        return _remembered_signin_identity(
            EVENT_SIGNIN_COOKIE_TYPE_USER,
            request.user,
            request.user.first_name,
            _event_signin_data_from_user(request.user),
        )

    return _remembered_signin_identity_from_cookie(request)


def _save_event_signin(event, signin_data):
    existing_signin = EventSignIn.objects.filter(
        event=event,
        email__iexact=signin_data["email"],
    ).first()
    if existing_signin is None:
        existing_signin = EventSignIn(event=event, email=signin_data["email"])

    existing_signin.first_name = signin_data["first_name"]
    existing_signin.last_name = signin_data["last_name"]
    existing_signin.zip_code = signin_data["zip_code"]
    existing_signin.newsletter_opt_in = signin_data["newsletter_opt_in"]
    existing_signin.save()
    return existing_signin


def _set_event_signin_identity_cookie(response, request, signin):
    if request.user.is_authenticated and request.user.email.lower() == signin.email.lower():
        set_event_signin_cookie(
            response,
            {"type": EVENT_SIGNIN_COOKIE_TYPE_USER, "id": request.user.id},
        )
    else:
        set_event_signin_cookie(
            response,
            {"type": EVENT_SIGNIN_COOKIE_TYPE_SIGNIN, "id": str(signin.id)},
        )


def _event_signin_redirect(request, event):
    if request.GET.get("kiosk", False):
        return redirect("event_signin_kiosk_postroll", event_slug_or_id=event.slug)
    return HttpResponseRedirect("/")


class EventsListView(ListView):
    model = ScheduledEvent
    paginate_by = 10

    def get_queryset(self):
        queryset = ScheduledEvent.objects.all()
        queryset = queryset.exclude(status=ScheduledEvent.Status.DELETED)
        queryset = queryset.exclude(hidden=True)
        queryset = queryset.filter(
            start_datetime__gte=datetime.datetime.now() - datetime.timedelta(hours=3)
        )
        queryset = queryset.order_by("start_datetime")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["feed_url"] = (
            self.request.build_absolute_uri(reverse("events_feed_all"))
            .replace("https://", "webcal://")
            .replace("http://", "webcal://")
        )
        context["feed_url_encoded"] = quote_plus(
            self.request.build_absolute_uri(reverse("events_feed_all"))
            .replace("https://", "webcal://")
            .replace("http://", "webcal://")
        )
        return context


class PastEventsListView(ListView):
    model = ScheduledEvent
    paginate_by = 10

    def get_queryset(self):
        queryset = ScheduledEvent.objects.all()
        queryset = queryset.exclude(status=ScheduledEvent.Status.DELETED)
        queryset = queryset.exclude(hidden=True)
        queryset = queryset.filter(
            start_datetime__lte=datetime.datetime.now() - datetime.timedelta(hours=3)
        )
        queryset = queryset.order_by("-start_datetime")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["feed_url"] = (
            self.request.build_absolute_uri(reverse("events_feed_all"))
            .replace("https://", "webcal://")
            .replace("http://", "webcal://")
        )
        context["feed_url_encoded"] = quote_plus(
            self.request.build_absolute_uri(reverse("events_feed_all"))
            .replace("https://", "webcal://")
            .replace("http://", "webcal://")
        )
        context["past"] = True
        return context


class EventDetailView(DetailView):
    model = ScheduledEvent
    slug_field = "slug"

    def next_event(self, current_object):
        return (
            ScheduledEvent.objects.order_by("start_datetime")
            .exclude(status=ScheduledEvent.Status.DELETED)
            .exclude(pk=current_object.pk)
            .exclude(hidden=True)
            .filter(start_datetime__gte=current_object.start_datetime)
            .first()
        )

    def previous_event(self, current_object):
        return (
            ScheduledEvent.objects.order_by("-start_datetime")
            .exclude(status=ScheduledEvent.Status.DELETED)
            .exclude(pk=current_object.pk)
            .exclude(hidden=True)
            .filter(start_datetime__lte=current_object.start_datetime)
            .first()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_event"] = self.next_event(self.object)
        context["previous_event"] = self.previous_event(self.object)
        return context


def event_view(request, event_slug_or_id):
    event = _fetch_event_by_slug_or_id(event_slug_or_id)
    if event is None:
        raise Http404
    html = "<html><body>%s</body></html>" % str(event)
    return HttpResponse(html)


def event_rsvp(request, event_slug_or_id):
    event = _fetch_event_by_slug_or_id(event_slug_or_id)
    if event is None:
        raise Http404
    if timezone.now() > event.start_datetime + datetime.timedelta(hours=6):
        return HttpResponseRedirect(request.path_info)

    if request.user.is_authenticated:
        rsvp, created = EventRSVP.objects.update_or_create(event=event, user=request.user)
        rsvp.save()
        return HttpResponseRedirect(reverse("event_detail", kwargs={"slug": event.slug}))

    if request.method == "POST":
        form = EventRSVPForm(request.POST)
        if form.is_valid():
            form.instance.event = event
            form.save()
            return HttpResponseRedirect(reverse("event_detail", kwargs={"slug": event.slug}))
    else:
        form = EventRSVPForm()
    return render(
        request,
        "form.html",
        context={
            "event": event,
            "form": form,
            "form_title": f"RSVP for {event}",
            "form_footer": (
                "After RSVPing, you may be contacted by PBA with info "
                "specifically related to this event."
            ),
        },
    )


def event_rsvp_cancel(request, event_slug_or_id):
    event = _fetch_event_by_slug_or_id(event_slug_or_id)
    if event is None:
        raise Http404
    if timezone.now() > event.start_datetime + datetime.timedelta(hours=6):
        return HttpResponseRedirect(request.path_info)

    if request.user.is_authenticated and event in request.user.profile.events:
        EventRSVP.objects.filter(user=request.user, event=event).delete()
        return HttpResponseRedirect(reverse("event_detail", kwargs={"slug": event.slug}))


def event_signin(request, event_slug_or_id):
    event = _fetch_event_by_slug_or_id(event_slug_or_id)
    if event is None:
        raise Http404
    remembered_identity = _event_signin_identity(request)
    if request.method == "POST":
        if (
            "quick_signin" in request.POST
            and remembered_identity is not None
            and remembered_identity["complete"]
        ):
            signin = _save_event_signin(event, remembered_identity["data"])
            response = _event_signin_redirect(request, event)
            _set_event_signin_identity_cookie(response, request, signin)
            return response

        form = EventSignInForm(request.POST)
        if form.is_valid():
            signin = _save_event_signin(event, _event_signin_data_from_signin(form.instance))
            response = _event_signin_redirect(request, event)
            _set_event_signin_identity_cookie(response, request, signin)
            return response
    elif timezone.now() > event.start_datetime + datetime.timedelta(days=1):
        return HttpResponseRedirect("/")
    else:
        form = EventSignInForm(initial=remembered_identity["data"] if remembered_identity else None)

    return render(
        request,
        "signin.html",
        context={
            "event": event,
            "form": form,
            "remembered_identity": remembered_identity,
            "quick_signin_identity": (
                remembered_identity
                if remembered_identity is not None and remembered_identity["complete"]
                else None
            ),
        },
    )


def event_signin_kiosk_postroll(request, event_slug_or_id):
    event = _fetch_event_by_slug_or_id(event_slug_or_id)
    if event is None:
        raise Http404
    return render(request, "signin-kiosk-postroll.html", context={"event": event})
