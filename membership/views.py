import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from djstripe.models import (
    Customer,
    PaymentMethod,
    Price,
    Product,
    Session,
    Subscription,
)

from membership.forms import RecurringDonationSetupForm
from membership.models import Donation, DonationProduct, DonationTier
from pbaabp.tasks import create_pba_account

_CUSTOM_FIELDS = [
    {
        "key": "first_name",
        "label": {"type": "custom", "custom": "First Name"},
        "type": "text",
        "text": {"maximum_length": 128},
    },
    {
        "key": "last_name",
        "label": {"type": "custom", "custom": "Last Name"},
        "type": "text",
        "text": {"maximum_length": 128},
    },
    {
        "key": "newsletter_opt_in",
        "label": {"type": "custom", "custom": "Newsletter Opt In"},
        "type": "dropdown",
        "dropdown": {"options": [{"label": "Yes", "value": 1}, {"label": "No", "value": 0}]},
    },
]

_CUSTOM_TEXT = {
    "terms_of_service_acceptance": {
        "message": (
            "I have read the Philly Bike Action "
            "[Code of Conduct](https://apps.bikeaction.org/policies/code-of-conduct/) "
            "and "
            "[Privacy and Data Statement](https://apps.bikeaction.org/policies/privacy-and-data/)."
        ),
    }
}


@csrf_exempt
def create_checkout_session(request, price_id=None):
    if request.method == "POST":
        stripe.api_key = settings.STRIPE_SECRET_KEY
        customer = None
        if request.user.is_authenticated:
            customer, _ = Customer.get_or_create(request.user)
        session = stripe.checkout.Session.create(
            ui_mode="embedded",
            mode="subscription" if price_id is not None else "setup",
            currency="USD",
            line_items=[{"price": price_id, "quantity": 1}] if price_id is not None else None,
            return_url=request.build_absolute_uri(reverse("complete_checkout_session")),
            customer=customer.id if customer else None,
            billing_address_collection="required" if customer is None else "auto",
            custom_fields=_CUSTOM_FIELDS if customer is None else None,
            custom_text=_CUSTOM_TEXT if customer is None else None,
            consent_collection={"terms_of_service": "required"} if customer is None else None,
        )
        request.session["_stripe_checkout_session_id"] = session.id
        return JsonResponse({"clientSecret": session.client_secret})
    else:
        context = {"stripe_public_key": settings.STRIPE_PUBLIC_KEY, "price_id": price_id}
        return TemplateResponse(request, "checkout_session.html", context)


@csrf_exempt
def create_setup_session(request):
    if request.method == "POST":
        stripe.api_key = settings.STRIPE_SECRET_KEY
        customer = None
        if request.user.is_authenticated:
            customer, _ = Customer.get_or_create(request.user)
        session = stripe.checkout.Session.create(
            ui_mode="embedded",
            mode="setup",
            currency="USD",
            return_url=request.build_absolute_uri(reverse("complete_checkout_session")),
            customer=customer.id,
        )
        request.session["_stripe_checkout_session_id"] = session.id
        return JsonResponse({"clientSecret": session.client_secret})
    else:
        context = {"stripe_public_key": settings.STRIPE_PUBLIC_KEY}
        return TemplateResponse(request, "setup_session.html", context)


def complete_checkout_session(request):
    checkout_session_id = request.session.pop("_stripe_checkout_session_id", default=None)
    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.retrieve(checkout_session_id)

    if session["status"] == "complete":
        if session.get("setup_intent", None):
            setup_intent = stripe.SetupIntent.retrieve(session["setup_intent"])
            payment_method = PaymentMethod._get_or_retrieve(setup_intent["payment_method"])
        elif session.get("subscription", None):
            subscription = Subscription._get_or_retrieve(session["subscription"])
            if not request.user.is_authenticated:
                custom_fields = {d["key"]: d[d["type"]]["value"] for d in session["custom_fields"]}
                first_name = custom_fields["first_name"]
                last_name = custom_fields["last_name"]
                email = session["customer_details"]["email"]
                street_address = session["customer_details"]["address"]["line1"]
                zip_code = session["customer_details"]["address"]["postal_code"]
                newsletter_opt_in = bool(int(custom_fields["newsletter_opt_in"]))

                user = get_user_model().objects.filter(email=email).first()
                if user is None:
                    user = create_pba_account(
                        first_name=first_name,
                        last_name=last_name,
                        street_address=street_address,
                        zip_code=zip_code,
                        email=email,
                        newsletter_opt_in=newsletter_opt_in,
                        subscription=True,
                        _return=True,
                    )
                    login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])

                stripe_customer = stripe.Customer.retrieve(subscription.customer.id)
                customer = Customer._get_or_retrieve(stripe_customer["id"])
                customer.subscriber = user
                customer.save()
            payment_method = subscription.default_payment_method
            if subscription.customer.default_payment_method is None:
                subscription.customer.add_payment_method(payment_method, set_default=True)
    return redirect("profile")


@csrf_exempt
def create_one_time_donation_checkout_session(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    if donation_product_id := request.GET.get("donation_product_id", None):
        donation_product = get_object_or_404(DonationProduct, id=donation_product_id)
        product = donation_product.stripe_product
        stripe_product = donation_product.stripe_product
    else:
        product = Product.objects.filter(name="One-Time Donation", active=True).first()

    if product is None:
        stripe_product_search = stripe.Product.search(
            query="active:'true' AND name:'One-Time Donation'"
        )
        if len(stripe_product_search["data"]) > 1:
            raise LookupError("Incorrect number of stripe products found")
        if len(stripe_product_search["data"]) < 1:
            stripe_product = stripe.Product.create(
                name="One-Time Donation",
                active=True,
                description=(
                    "One-Time Donation to Philly Bike Action, "
                    "a social welfare organization incorporated in the "
                    "Commonwealth of Pennsylvania. "
                    "Contributions to Philly Bike Action are not deductible "
                    "as charitable contributions for federal income tax purposes."
                ),
                shippable=False,
                statement_descriptor="Philly Bike Action",
            )
        else:
            stripe_product = stripe.Product.retrieve(stripe_product_search["data"][0]["id"])

        product = Product()._get_or_retrieve(stripe_product.id)

    price = Price.objects.filter(product=product, unit_amount=None, type="one_time").first()
    if price is None:
        price_search = [
            p
            for p in stripe.Price.search(query=f"product:'{stripe_product.id}'")["data"]
            if p.get("type", None) == "one_time" and p.get("custom_unit_amount", None) is not None
        ]
        if len(price_search) > 1:
            raise LookupError("Incorrect number of stripe prices found")
        elif len(price_search) < 1:
            price = Price.create(
                product=product,
                currency="USD",
                custom_unit_amount={
                    "enabled": True,
                    "preset": 2500,
                    "minimum": 1000,
                    "maximum": 100000,
                },
                unit_amount=None,
            )
        else:
            price = Price()._get_or_retrieve(price_search[0]["id"])

    if request.method == "POST":
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            ui_mode="embedded",
            mode="payment",
            currency="USD",
            line_items=[{"price": price.id, "quantity": 1}],
            return_url=request.build_absolute_uri(
                reverse("complete_one_time_donation_checkout_session")
            ),
            custom_fields=[
                {
                    "key": "comment",
                    "label": {"type": "custom", "custom": "Comment"},
                    "optional": True,
                    "type": "text",
                    "text": {"maximum_length": 255},
                }
            ],
            customer=(
                request.user.djstripe_customers.first().id
                if request.user.is_authenticated and request.user.djstripe_customers.first()
                else None
            ),
            customer_email=(
                request.user.email
                if request.user.is_authenticated and not request.user.djstripe_customers.first()
                else None
            ),
        )
        request.session["_stripe_checkout_session_id"] = session.id
        return JsonResponse({"clientSecret": session.client_secret})
    else:
        request.session["_redirect_after_donation"] = request.META.get("HTTP_REFERER", None)
        context = {
            "stripe_public_key": settings.STRIPE_PUBLIC_KEY,
            "donation_product_id": donation_product_id,
        }
        return TemplateResponse(request, "checkout_session.html", context)


def complete_one_time_donation_checkout_session(request):
    checkout_session_id = request.session.pop("_stripe_checkout_session_id", default=None)
    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.retrieve(checkout_session_id, expand=["line_items"])
    if session["status"] == "complete":
        _session = Session()._get_or_retrieve(session["id"], expand=["line_items"])
        _session.save()
        _line_items = _session.line_items.get("data")
        if _line_items is None:
            _line_items = _session.line_items
        donation_products = DonationProduct.objects.filter(
            stripe_product__id__in=[li["price"]["product"] for li in _line_items]
        ).all()
        if donation_products:
            for line_item in _line_items:
                donation_product = DonationProduct.objects.filter(
                    stripe_product__id=line_item["price"]["product"]
                ).first()
                if donation_product:
                    _d = Donation(
                        donation_product=donation_product, amount=line_item["amount_total"] / 100
                    )
                    _d.save()
        custom_fields = {d["key"]: d[d["type"]]["value"] for d in session["custom_fields"]}
        if custom_fields.get("comment"):
            _d = Donation(
                amount=_line_items[0]["amount_total"] / 100, comment=custom_fields.get("comment")
            )
            _d.save()
        if redirect_to := request.session.pop("_redirect_after_donation", default=None):
            messages.add_message(request, messages.INFO, "Thank you for your donation!")
            return redirect(redirect_to)
        return redirect("index")
    return redirect("index")


@login_required
def card_remove(request, payment_method_id):
    method = PaymentMethod.objects.filter(id=payment_method_id).first()
    if method is not None:
        method.detach()
    return redirect("profile")


@login_required
def card_make_default(request, payment_method_id):
    method = PaymentMethod.objects.filter(id=payment_method_id).first()
    if method is not None:
        method.customer.add_payment_method(method, set_default=True)
    return redirect("profile")


def setup_recurring_donation(request, donation_tier_id=None):
    if request.method == "POST":
        form = RecurringDonationSetupForm(request.POST)
        if form.is_valid():
            donation_tier = DonationTier.objects.get(id=form.cleaned_data["donation_tier"])
            return redirect(
                "create_subscription_checkout_session", price_id=donation_tier.stripe_price.id
            )
    else:
        form = RecurringDonationSetupForm()
        context = {"form": form}
        return TemplateResponse(request, "setup_recurring_donation.html", context)


@login_required
def cancel_recurring_donation(request, subscription_id=None):
    subscription = Subscription.objects.filter(id=subscription_id).first()
    if subscription is not None:
        subscription.cancel()
    return redirect("profile")


@login_required
def change_recurring_donation(request, subscription_id=None):
    existing_subscription = request.user.djstripe_customers.first().active_subscriptions.first()
    existing_tier = DonationTier.objects.filter(
        stripe_price__id=existing_subscription.plan.id
    ).first()

    subscription = Subscription.objects.filter(id=subscription_id).first()
    if request.method == "POST":
        if subscription is not None:
            form = RecurringDonationSetupForm(request.POST)
            if form.is_valid():
                donation_tier = DonationTier.objects.get(id=form.cleaned_data["donation_tier"])
                if donation_tier == existing_tier:
                    messages.add_message(
                        request, messages.INFO, "You are already subscribed to that donation tier"
                    )
                    return redirect("change_recurring_donation", subscription_id=subscription_id)
            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe_subscription = stripe.Subscription.retrieve(subscription.id)
            stripe.SubscriptionItem.modify(
                stripe_subscription["items"]["data"][0]["id"],
                price=donation_tier.stripe_price.id,
                proration_behavior="none",
            )
            stripe_subscription = stripe.Subscription.retrieve(subscription.id)
            subscription = Subscription.sync_from_stripe_data(stripe_subscription)
            return redirect("profile")
    else:
        form = RecurringDonationSetupForm(tier_id=existing_tier.id if existing_tier else None)
        context = {"form": form}
        return TemplateResponse(request, "change_recurring_donation.html", context)


@login_required
def charge_history_partial(request):
    customer = request.user.djstripe_customers.first()
    if customer:
        try:
            customer._sync_subscriptions()
            customer._sync_charges()
        except Exception:
            pass
        charges = customer.charges.order_by("-created").all()
    else:
        charges = []
    return render(request, "_donation_history_partial.html", {"charges": charges})


@login_required
def charge_history(request):
    return render(request, "donation_history.html")
