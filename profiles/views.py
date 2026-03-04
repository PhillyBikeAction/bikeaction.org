import requests
import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from djstripe.models import Customer, Price

from organizers.models import OrganizerApplication
from pbaabp.integrations.mailjet import Mailjet
from profiles.forms import ProfileUpdateForm
from profiles.models import DoNotEmail, Profile, ShirtOrder
from projects.models import ProjectApplication


class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = Profile

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        import datetime

        from django.utils import timezone

        from elections.models import Ballot, Election, Nomination, Nominee

        context = super().get_context_data(**kwargs)
        context["today"] = timezone.now().date()
        upcoming_election = Election.get_upcoming()
        if upcoming_election:
            context["upcoming_election"] = upcoming_election
            context["current_eligibility"] = self.request.user.profile.eligible_as_of(
                timezone.now()
            )
            context["election_eligibility"] = self.request.user.profile.eligible_as_of(
                upcoming_election.membership_eligibility_deadline
            )
            # Calculate the earliest date for Discord activity to be valid
            context["discord_activity_start_date"] = (
                upcoming_election.membership_eligibility_deadline - datetime.timedelta(days=30)
            )

        # Get nomination data (with social accounts prefetched for Discord handles)
        context["nominations_given"] = (
            Nomination.objects.filter(nominator=self.request.user, draft=False)
            .select_related("nominee__election", "nominee__user")
            .prefetch_related("nominee__user__socialaccount_set")
        )

        nominations_received_pending = (
            Nomination.objects.filter(
                nominee__user=self.request.user,
                draft=False,
                acceptance_status=Nomination.AcceptanceStatus.PENDING,
            )
            .select_related("nominee__election", "nominator")
            .prefetch_related("nominator__socialaccount_set")
        )
        context["nominations_received_pending"] = nominations_received_pending

        # Get unique nominees with pending nominations for profile edit link
        context["pending_nominees"] = (
            Nominee.objects.filter(
                user=self.request.user, nominations__in=nominations_received_pending
            )
            .distinct()
            .select_related("election")
        )

        nominations_received_responded = (
            Nomination.objects.filter(
                nominee__user=self.request.user,
                draft=False,
            )
            .exclude(acceptance_status=Nomination.AcceptanceStatus.PENDING)
            .select_related("nominee__election", "nominator")
            .prefetch_related("nominator__socialaccount_set")
        )
        context["nominations_received_responded"] = nominations_received_responded

        # Get unique nominees with responded nominations for profile edit link
        context["responded_nominees"] = (
            Nominee.objects.filter(
                user=self.request.user, nominations__in=nominations_received_responded
            )
            .distinct()
            .select_related("election")
        )

        context["nomination_drafts"] = (
            Nomination.objects.filter(nominator=self.request.user, draft=True)
            .select_related("nominee__election", "nominee__user")
            .prefetch_related("nominee__user__socialaccount_set")
        )

        # Get elections where user can nominate (nominations open + was eligible at deadline)
        open_nomination_elections = []
        all_elections = Election.objects.filter(nominations_close__gte=timezone.now()).order_by(
            "nominations_close"
        )

        for election in all_elections:
            if election.is_nominations_open():
                eligibility = self.request.user.profile.eligible_as_of(
                    election.membership_eligibility_deadline
                )
                if eligibility["eligible"]:
                    open_nomination_elections.append(election)

        context["open_nomination_elections"] = open_nomination_elections

        # Check for open voting elections where user is eligible
        voting_open_elections = Election.objects.filter(
            voting_opens__lte=timezone.now(), voting_closes__gt=timezone.now()
        ).order_by("voting_closes")

        for election in voting_open_elections:
            # Check if user was eligible as of membership deadline
            eligible_voters = election.get_eligible_voters()
            if self.request.user.profile in eligible_voters:
                context["voting_open_election"] = election
                # Check if user has already voted
                context["user_ballot"] = Ballot.objects.filter(
                    election=election, voter=self.request.user
                ).first()
                break

        return context


class ProfileDistrictAndRCOPartial(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = "profiles/_rcos_partial.html"

    def get_object(self, queryset=None):
        return self.request.user.profile


class ProfileDonationsPartial(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = "profiles/_donations_partial.html"

    def get_object(self, queryset=None):
        try:
            customer = Customer.objects.filter(subscriber=self.request.user).first()
            if customer:
                customer.api_retrieve()
                customer._sync_subscriptions()
                customer._sync_charges()
        except Exception:
            pass
        return self.request.user.profile


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileUpdateForm

    def get_success_url(self):
        return reverse("profile")

    def get_object(self):
        return Profile.objects.get(user=self.request.user)


class ShirtsAreDoneMixin:
    def dispatch(self, request, *args, **kwargs):
        messages.add_message(self.request, messages.INFO, "T-Shirt orders are closed")
        return HttpResponseRedirect(reverse("profile"))


class ShirtOrderView(LoginRequiredMixin, ShirtsAreDoneMixin, CreateView):
    model = ShirtOrder
    fields = ["product_type", "fit", "print_color", "size"]

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.save()
        product_name = (
            "T-Shirt" if obj.product_type == ShirtOrder.ProductType.T_SHIRT else "Sweatshirt"
        )
        messages.add_message(
            self.request,
            messages.INFO,
            f"{product_name} order recorded! Complete payment to finalize.",
        )
        self.obj = obj
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("shirt_pay", kwargs={"shirt_id": self.obj.id})


class ShirtOrderDeleteView(LoginRequiredMixin, ShirtsAreDoneMixin, DeleteView):
    model = ShirtOrder

    def get_success_url(self):
        messages.add_message(self.request, messages.INFO, "Order deleted.")
        return reverse("profile")


@csrf_exempt
def create_tshirt_checkout_session(request, shirt_id):
    # Close shirt orders
    messages.add_message(request, messages.INFO, "Sorry, shirt orders are closed!")
    return HttpResponseRedirect(reverse("profile"))

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Get the shirt order to determine product type
    shirt = ShirtOrder.objects.get(id=shirt_id)

    # Search for appropriate Stripe product based on product type
    if shirt.product_type == ShirtOrder.ProductType.SWEATSHIRT:
        product_search_query = "active:'true' AND name:'Sweatshirt Pre-Order 2025-10'"
        product_name = "Sweatshirt"
    else:
        product_search_query = "active:'true' AND name:'T-Shirt Pre-Order 2025-10'"
        product_name = "T-Shirt"

    stripe_product_search = stripe.Product.search(query=product_search_query)

    if not stripe_product_search["data"]:
        messages.add_message(
            request,
            messages.ERROR,
            f"'{product_name} Pre-Order 2025-10' not found. Please contact apps@bikeaction.org.",
        )
        return HttpResponseRedirect(reverse("profile"))

    price_search = [
        p
        for p in stripe.Price.search(query=f"product:'{stripe_product_search['data'][0]['id']}'")[
            "data"
        ]
    ]

    if not price_search:
        messages.add_message(
            request,
            messages.ERROR,
            f"No price found for {product_name}. Please contact apps@bikeaction.org.",
        )
        return HttpResponseRedirect(reverse("profile"))

    price = Price()._get_or_retrieve(price_search[0]["id"])

    if request.method == "POST":
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            ui_mode="embedded",
            mode="payment",
            currency="USD",
            line_items=[{"price": price.id, "quantity": 1}],
            return_url=request.build_absolute_uri(
                reverse("shirt_pay_complete", kwargs={"shirt_id": shirt_id})
            ),
            shipping_address_collection={"allowed_countries": ["US"]},
            customer=(
                request.user.djstripe_customers.first().id
                if request.user.is_authenticated and request.user.djstripe_customers.first()
                else None
            ),
            allow_promotion_codes=True,
        )
        request.session["_stripe_checkout_session_id"] = session.id
        return JsonResponse({"clientSecret": session.client_secret})
    else:
        context = {"stripe_public_key": settings.STRIPE_PUBLIC_KEY, "shirt": shirt}
        return TemplateResponse(request, "tshirt_checkout_session.html", context)


def complete_tshirt_checkout_session(request, shirt_id):
    checkout_session_id = request.session.pop("_stripe_checkout_session_id", default=None)
    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.retrieve(checkout_session_id)
    if session["status"] == "complete":
        s = ShirtOrder.objects.get(id=shirt_id)
        s.billing_details = session["customer_details"]
        s.shipping_details = session["shipping_details"]
        s.paid = True
        s.save()
        product_name = (
            "T-Shirt" if s.product_type == ShirtOrder.ProductType.T_SHIRT else "Sweatshirt"
        )
        messages.add_message(request, messages.INFO, f"{product_name} paid!")
        return HttpResponseRedirect(reverse("profile"))
    messages.add_message(request, messages.ERROR, "Payment incomplete!")
    return HttpResponseRedirect(reverse("profile"))


class ProfileDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    template_name = "profiles/profile_confirm_delete.html"

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = Customer.objects.filter(subscriber=self.request.user).first()
        context["has_active_subscription"] = False
        if customer:
            active_subscriptions = customer.active_subscriptions.all()
            context["has_active_subscription"] = active_subscriptions.exists()
            context["active_subscriptions"] = active_subscriptions

        context["has_project_applications"] = ProjectApplication.objects.filter(
            submitter=self.request.user
        ).exists()
        context["has_organizer_applications"] = OrganizerApplication.objects.filter(
            submitter=self.request.user
        ).exists()
        context["has_applications"] = (
            context["has_project_applications"] or context["has_organizer_applications"]
        )

        profile = self.request.user.profile
        context["newsletter_subscribed"] = profile.newsletter_opt_in

        mailjet = Mailjet()
        contact_lists = mailjet.fetch_contact_lists(self.request.user.email)
        context["mailjet_subscribed"] = any(
            cl["ListID"] == int(settings.MAILJET_CONTACT_LIST_ID) and cl["IsUnsub"] is False
            for cl in contact_lists.get("Data", [])
        )

        return context

    def get_success_url(self):
        return reverse("index")

    def post(self, request, *args, **kwargs):
        customer = Customer.objects.filter(subscriber=request.user).first()
        if customer and customer.active_subscriptions.exists():
            messages.add_message(
                request,
                messages.ERROR,
                "You cannot delete your account while you have active subscriptions. "
                "Please cancel your subscriptions first.",
            )
            return HttpResponseRedirect(reverse("profile"))

        project_apps = ProjectApplication.objects.filter(submitter=request.user)
        organizer_apps = OrganizerApplication.objects.filter(submitter=request.user)

        if project_apps.exists() or organizer_apps.exists():
            messages.add_message(
                request,
                messages.ERROR,
                "You cannot delete your account while you have project or organizer applications. "
                "Please contact apps@bikeaction.org for assistance.",
            )
            return HttpResponseRedirect(reverse("profile"))

        user = self.get_object()

        DoNotEmail.objects.get_or_create(
            email=user.email, defaults={"reason": DoNotEmail.Reason.ACCOUNT_DELETION}
        )

        list_id = settings.MAILJET_CONTACT_LIST_ID
        url = f"https://api.mailjet.com/v3/REST/contactslist/{list_id}/managecontact"

        requests.post(
            url,
            json={"Action": "remove", "Email": user.email},
            auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
        )
        requests.post(
            url,
            json={"Action": "unsub", "Email": user.email},
            auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
        )

        return super().post(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        user = self.get_object()

        do_not_email, created = DoNotEmail.objects.get_or_create(
            email=user.email, defaults={"reason": DoNotEmail.Reason.ACCOUNT_DELETION}
        )

        messages.add_message(request, messages.SUCCESS, "Account deleted")

        return super().delete(request, *args, **kwargs)
