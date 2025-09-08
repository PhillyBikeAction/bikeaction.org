import datetime
import uuid
from urllib.parse import quote_plus

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView

from events.forms import EventRSVPForm, EventSignInForm
from events.models import EventRSVP, EventSignIn, ScheduledEvent


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
    if request.method == "POST":
        form = EventSignInForm(request.POST)
        if form.is_valid():
            # Check for a previous submission
            existing_signin = EventSignIn.objects.filter(
                event=event, email__iexact=form.instance.email
            ).first()
            if existing_signin is not None:
                existing_signin.first_name = form.instance.first_name
                existing_signin.last_name = form.instance.last_name
                existing_signin.council_district = form.instance.council_district
                existing_signin.zip_code = form.instance.zip_code
                existing_signin.newsletter_opt_in = form.instance.newsletter_opt_in
                existing_signin.save()
            else:
                form.instance.event = event
                form.save()

            if request.GET.get("kiosk", False):
                return redirect("event_signin_kiosk_postroll", event_slug_or_id=event.slug)
            else:
                return HttpResponseRedirect("/")
    elif timezone.now() > event.start_datetime + datetime.timedelta(days=1):
        return HttpResponseRedirect("/")
    else:
        form = EventSignInForm()

    return render(request, "signin.html", context={"event": event, "form": form})


def event_signin_kiosk_postroll(request, event_slug_or_id):
    event = _fetch_event_by_slug_or_id(event_slug_or_id)
    if event is None:
        raise Http404
    return render(request, "signin-kiosk-postroll.html", context={"event": event})
