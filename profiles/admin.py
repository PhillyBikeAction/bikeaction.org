import csv
import datetime
from collections import defaultdict
from io import BytesIO

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from django.utils.safestring import mark_safe
from djstripe.models import Subscription
from email_log.models import Email
from reportlab.lib.units import inch as rl_inch
from reportlab.pdfgen import canvas

from facets.models import District, RegisteredCommunityOrganization
from membership.models import Membership
from pbaabp.admin import ReadOnlyLeafletGeoAdminMixin, organizer_admin
from profiles.models import DiscordActivity, DoNotEmail, Profile, ShirtOrder


class DistrictOrganizerFilter(admin.SimpleListFilter):
    title = "district organizer"
    parameter_name = "is_organizer"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        if self.value() == "True":
            return queryset.exclude(
                organized_districts=None,
            )
        elif self.value() == "False":
            return queryset.filter(organized_districts=None)
        return queryset


class DistrictOrganizerUserFilter(admin.SimpleListFilter):
    title = "district organizer"
    parameter_name = "is_organizer"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        if self.value() == "True":
            return queryset.exclude(
                profile__organized_districts=None,
            )
        elif self.value() == "False":
            return queryset.filter(profile__organized_districts=None)
        return queryset


class ProfileCompleteFilter(admin.SimpleListFilter):
    title = "profile complete"
    parameter_name = "profile_complete"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        if self.value() in (
            "True",
            True,
        ):
            return queryset.filter(
                street_address__isnull=False,
                zip_code__isnull=False,
            )
        elif self.value() in (
            "False",
            False,
        ):
            return queryset.filter(Q(street_address__isnull=True) | Q(zip_code__isnull=True))
        return queryset


class NewsletterSubscriberFilter(admin.SimpleListFilter):
    title = "subscribed to newsletter"
    parameter_name = "newsletter subscriber"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        if self.value() in (
            "True",
            True,
        ):
            return queryset.filter(
                newsletter_opt_in=True,
            )
        elif self.value() in (
            "False",
            False,
        ):
            return queryset.filter(
                newsletter_opt_in=False,
            )
        return queryset


class GeolocatedFilter(admin.SimpleListFilter):
    title = "geolocated"
    parameter_name = "geolocated"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        if self.value() in (
            "True",
            True,
        ):
            return queryset.filter(
                location__isnull=False,
            )
        elif self.value() in (
            "False",
            False,
        ):
            return queryset.filter(Q(location__isnull=True))
        return queryset


class AppsConnectedFilter(admin.SimpleListFilter):
    title = "apps connected"
    parameter_name = "apps_connected"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        if self.value() in (
            "True",
            True,
        ):
            return queryset.annotate(total=Count("user__socialaccount")).filter(total__gt=0)
        elif self.value() in (
            "False",
            False,
        ):
            return queryset.annotate(total=Count("user__socialaccount")).filter(total=0)
        return queryset


class MemberFilter(admin.SimpleListFilter):
    title = "PBA Member"
    parameter_name = "member"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        # Use pre-computed annotations from get_queryset for better performance
        if self.value() in (
            "True",
            True,
        ):
            return queryset.filter(
                Q(has_discord_activity=True)
                | Q(has_active_subscription=True)
                | Q(has_special_membership=True)
            )
        elif self.value() in (
            "False",
            False,
        ):
            return queryset.filter(
                has_discord_activity=False,
                has_active_subscription=False,
                has_special_membership=False,
            )
        return queryset


class MemberByDonationFilter(admin.SimpleListFilter):
    title = "PBA Member (donation)"
    parameter_name = "member_donation"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        # Use pre-computed annotation for better performance
        if self.value() in (
            "True",
            True,
        ):
            return queryset.filter(has_active_subscription=True)
        elif self.value() in (
            "False",
            False,
        ):
            return queryset.filter(has_active_subscription=False)
        return queryset


class MemberByDiscordActivityFilter(admin.SimpleListFilter):
    title = "PBA Member (discord)"
    parameter_name = "member_discord"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        # Use pre-computed annotation for better performance
        if self.value() in (
            "True",
            True,
        ):
            return queryset.filter(has_discord_activity=True)
        elif self.value() in (
            "False",
            False,
        ):
            return queryset.filter(has_discord_activity=False)
        return queryset


class MemberBySpecialRecognitionFilter(admin.SimpleListFilter):
    title = "PBA Member (special recognition)"
    parameter_name = "member_special"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        # Use pre-computed annotation for better performance
        if self.value() in (
            "True",
            True,
        ):
            return queryset.filter(has_special_membership=True)
        elif self.value() in (
            "False",
            False,
        ):
            return queryset.filter(has_special_membership=False)
        return queryset


class DistrictFilter(admin.SimpleListFilter):
    title = "Council District (verified)"
    parameter_name = "council_district_verified"

    def lookups(self, request, model_admin):
        return [(f.id, f.name) for f in District.objects.all() if f.targetable]

    def queryset(self, request, queryset):
        if self.value():
            d = District.objects.get(id=self.value())
            return queryset.filter(location__within=d.mpoly)
        return queryset


class OrganizerDistrictFilter(DistrictFilter):
    def lookups(self, request, model_amin):
        return [
            (f.id, f.name) for f in request.user.profile.organized_districts.all() if f.targetable
        ]


class RCOFilter(admin.SimpleListFilter):
    title = "RCOs (verified)"
    parameter_name = "rcos_verified"

    def lookups(self, request, model_admin):
        return [
            (f.id, f.name) for f in RegisteredCommunityOrganization.objects.all() if f.targetable
        ]

    def queryset(self, request, queryset):
        if self.value():
            r = RegisteredCommunityOrganization.objects.get(id=self.value())
            return queryset.filter(location__within=r.mpoly)
        return queryset


class EmailHistory:
    """Custom class to display email history in Profile admin"""

    def __init__(self, profile):
        self.profile = profile

    def get_emails(self):
        if self.profile and self.profile.user.email:
            return Email.objects.filter(recipients__icontains=self.profile.user.email).order_by(
                "-date_sent"
            )[:50]  # Show last 50 emails
        return Email.objects.none()


class OrganizerRCOFilter(RCOFilter):
    def lookups(self, request, model_amin):
        return [
            (f.id, f.name)
            for district in request.user.profile.organized_districts.all()
            for f in district.intersecting_rcos.all()
            if f.targetable
        ]


class OrganizesDistrictInline(admin.TabularInline):
    model = District.organizers.through
    verbose_name = "District"
    verbose_name_plural = "Districts Organized"
    extra = 0


class ProfileAdmin(ReadOnlyLeafletGeoAdminMixin, admin.ModelAdmin):
    list_display = [
        "_name",
        "_user",
        "discord_handle",
        "profile_complete",
        "apps_connected",
        "geolocated",
        "council_district_display",
        "emails_last_30_days",
        "created_at",
        "street_address",
        "districts_organized",
    ]
    list_filter = [
        ProfileCompleteFilter,
        DistrictOrganizerFilter,
        MemberFilter,
        MemberByDonationFilter,
        MemberByDiscordActivityFilter,
        MemberBySpecialRecognitionFilter,
        NewsletterSubscriberFilter,
        AppsConnectedFilter,
        GeolocatedFilter,
        DistrictFilter,
        RCOFilter,
    ]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "user__socialaccount__extra_data__username",
        "street_address",
    ]
    inlines = [OrganizesDistrictInline]
    autocomplete_fields = ("user",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("user")

        # Use a subquery to count emails efficiently
        thirty_days_ago = timezone.now() - datetime.timedelta(days=30)

        # Create subquery that counts emails for each user
        email_count_subquery = Subquery(
            Email.objects.filter(
                recipients__icontains=OuterRef("user__email"), date_sent__gte=thirty_days_ago
            )
            .values("recipients")
            .annotate(count=Count("*"))
            .values("count")[:1],
            output_field=IntegerField(),
        )

        # Annotate with email count, defaulting to 0
        queryset = queryset.annotate(email_count_30d=Coalesce(email_count_subquery, Value(0)))

        # Pre-compute membership status flags to avoid expensive joins in filters
        now = timezone.now().date()

        # Check for active Stripe subscriptions
        has_active_subscription = Exists(
            Subscription.objects.filter(
                customer__subscriber=OuterRef("user"), status__in=["active"]
            )
        )

        # Check for Discord activity in last 30 days
        # Need both Discord connection AND recent activity
        has_discord_activity = Exists(
            DiscordActivity.objects.filter(
                profile=OuterRef("pk"), date__gte=(now - datetime.timedelta(days=30))
            ).filter(profile__user__socialaccount__provider="discord")
        )

        # Check for special recognition membership
        has_special_membership = Exists(
            Membership.objects.filter(user=OuterRef("user"), start_date__lte=now).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=now)
            )
        )

        queryset = queryset.annotate(
            has_active_subscription=has_active_subscription,
            has_discord_activity=has_discord_activity,
            has_special_membership=has_special_membership,
        )

        return queryset

    def _user(self, obj=None):
        if obj is None:
            return ""
        return obj.user.email

    def _name(self, obj=None):
        if obj is None:
            return ""
        return f"{obj.user.first_name} {obj.user.last_name}"

    def discord_handle(self, obj=None):
        if obj is None or obj.discord is None:
            return ""
        return obj.discord.extra_data["username"]

    def discord_activity(self, obj=None):
        if obj is None:
            return ""
        date_range_prev_60 = [
            timezone.now().date() - datetime.timedelta(days=(90 - i)) for i in range(60)
        ]
        date_range_last_30 = [
            timezone.now().date() - datetime.timedelta(days=(30 - i)) for i in range(31)
        ]
        query_prev_60 = DiscordActivity.objects.filter(
            profile=obj, date__in=date_range_prev_60
        ).all()
        query_last_30 = DiscordActivity.objects.filter(
            profile=obj, date__in=date_range_last_30
        ).all()
        counts_by_date_prev_60 = {activity.date: activity.count for activity in query_prev_60}
        counts_by_date_last_30 = {activity.date: activity.count for activity in query_last_30}
        counts_prev_60 = ",".join(
            [str(counts_by_date_prev_60.get(date, 0)) for date in date_range_prev_60]
        )
        counts_last_30 = ",".join(
            [str(counts_by_date_last_30.get(date, 0)) for date in date_range_last_30]
        )
        return mark_safe(
            f"""
            <div style="padding: 0; margin: 0; display: block; border-collapse: collapse;">
                <div
                    style="display: inline-block;"
                    data-sparkline="true"
                    data-points="{counts_prev_60}"
                    data-width="150"
                    data-height="50"
                    data-gap="0"
                ></div>
                <div
                    style="display: inline-block;"
                    data-colors="#83bd56"
                    data-sparkline="true"
                    data-points="{counts_last_30}"
                    data-width="75"
                    data-height="50"
                    data-gap="0"
                ></div>
            </div>
            """
        )

    discord_activity.help_text = "Discord activity over last 90 days, most recent 30 is in green"

    def geolocated(self, obj=None):
        if obj is None:
            return False
        return obj.location is not None

    geolocated.boolean = True

    def profile_complete(self, obj=None):
        if obj is None:
            return False
        return all(
            [
                obj.street_address is not None,
                obj.zip_code is not None,
            ]
        )

    profile_complete.boolean = True

    def districts_organized(self, obj=None):
        if obj is None:
            return ""
        return ", ".join([d.name.lstrip("District ") for d in obj.organized_districts.all()])

    def apps_connected(self, obj=None):
        if obj is None:
            return False
        return obj.discord is not None

    apps_connected.boolean = True

    def council_district_calculated(self, obj=None):
        return obj.district

    council_district_calculated.short_description = "Calculated District"

    def council_district_display(self, obj=None):
        if obj is None:
            return None
        return obj.district

    council_district_display.short_description = "District"

    def emails_last_30_days(self, obj=None):
        if obj is None:
            return 0
        # Use the annotated field from get_queryset
        return getattr(obj, "email_count_30d", 0)

    emails_last_30_days.short_description = "Emails (30d)"
    emails_last_30_days.admin_order_field = "email_count_30d"

    def active_subscription(self, obj=None):
        if obj is None:
            return None
        if customer := obj.user.djstripe_customers.first():
            print(customer)
            if subscription := customer.active_subscriptions.first():
                return (
                    f"${subscription.stripe_data['plan']['amount'] / 100:,.2f}/"
                    f"{subscription.stripe_data['plan']['interval']} "
                    f"since {subscription.created:%B %Y}"
                )
        return None

    def email_activity_sparkline(self, obj=None):
        if obj is None or not obj.user.email:
            return ""

        # Get date ranges for sparkline
        date_range_prev_60 = [
            timezone.now().date() - datetime.timedelta(days=(90 - i)) for i in range(60)
        ]
        date_range_last_30 = [
            timezone.now().date() - datetime.timedelta(days=(30 - i)) for i in range(31)
        ]

        # Query emails for the last 90 days
        ninety_days_ago = timezone.now().date() - datetime.timedelta(days=90)
        emails = Email.objects.filter(
            recipients__icontains=obj.user.email, date_sent__gte=ninety_days_ago
        ).values_list("date_sent", flat=True)

        # Count emails by date
        email_dates = [email.date() if hasattr(email, "date") else email for email in emails]
        counts_by_date = {}
        for date in email_dates:
            counts_by_date[date] = counts_by_date.get(date, 0) + 1

        # Build counts for sparklines
        counts_prev_60 = ",".join([str(counts_by_date.get(date, 0)) for date in date_range_prev_60])
        counts_last_30 = ",".join([str(counts_by_date.get(date, 0)) for date in date_range_last_30])

        return mark_safe(
            f"""
            <div style="padding: 0; margin: 0; display: block; border-collapse: collapse;">
                <div
                    style="display: inline-block;"
                    data-sparkline="true"
                    data-points="{counts_prev_60}"
                    data-width="150"
                    data-height="50"
                    data-gap="0"
                ></div>
                <div
                    style="display: inline-block;"
                    data-colors="#83bd56"
                    data-sparkline="true"
                    data-points="{counts_last_30}"
                    data-width="75"
                    data-height="50"
                    data-gap="0"
                ></div>
            </div>
            """
        )

    email_activity_sparkline.short_description = (
        "Email activity over last 90 days, most recent 30 is in green"
    )

    def email_history(self, obj=None):
        if obj is None or not obj.user.email:
            return "No emails found"

        emails = Email.objects.filter(recipients__icontains=obj.user.email).order_by("-date_sent")[
            :20
        ]

        if not emails:
            return "No emails found"

        html = '<div style="max-height: 400px; overflow-y: auto;">'
        html += '<table style="width: 100%; border-collapse: collapse;">'
        html += '<thead><tr style="background-color: #f0f0f0;">'
        html += (
            '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
            "Date Sent</th>"
        )
        html += (
            '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
            "Subject</th>"
        )
        html += (
            '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">From</th>'
        )
        html += "</tr></thead><tbody>"

        for email in emails:
            html += '<tr style="border-bottom: 1px solid #ddd;">'
            html += f'<td style="padding: 8px;">{email.date_sent.strftime("%Y-%m-%d %H:%M")}</td>'
            html += f'<td style="padding: 8px;">{email.subject}</td>'
            html += f'<td style="padding: 8px;">{email.from_email}</td>'
            html += "</tr>"

        html += "</tbody></table></div>"
        return mark_safe(html)

    email_history.short_description = "Email History (Last 20)"

    def donation_history(self, obj=None):
        if obj is None:
            return "No donation data"

        try:
            customer = obj.user.djstripe_customers.first()
            if not customer:
                return "No customer found in Stripe"

            # Try to sync data from Stripe
            try:
                customer.api_retrieve()
                customer._sync_subscriptions()
                customer._sync_charges()
            except Exception:
                # Continue even if sync fails, we'll show what we have
                pass

            html = '<div style="max-height: 600px; overflow-y: auto;">'

            # Calculate total from all succeeded charges
            charges = customer.charges.all()
            total_amount = sum(charge.amount for charge in charges if charge.status == "succeeded")

            if total_amount > 0:
                html += (
                    f'<h3 style="margin-top: 0; color: #417505;">'
                    f"Total Donated: ${total_amount:,.2f}</h3>"
                )

            # Subscriptions section
            subscriptions = customer.subscriptions.all().order_by("-created")
            subscription_count = subscriptions.count()

            if subscription_count > 0:
                html += f'<h4 style="margin-top: 0;">Subscriptions ({subscription_count})</h4>'
                html += (
                    '<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">'
                )
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += (
                    '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
                    "Plan</th>"
                )
                html += (
                    '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
                    "Status</th>"
                )
                html += (
                    '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
                    "Created</th>"
                )
                html += (
                    '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
                    "Current Period</th>"
                )
                html += "</tr></thead><tbody>"

                for subscription in subscriptions:
                    html += '<tr style="border-bottom: 1px solid #ddd;">'
                    html += f'<td style="padding: 8px;">{subscription.plan}</td>'
                    html += f'<td style="padding: 8px;">{subscription.status}</td>'
                    created = subscription.created.strftime("%Y-%m-%d")
                    html += f'<td style="padding: 8px;">{created}</td>'
                    if subscription.current_period_start and subscription.current_period_end:
                        period_start = subscription.current_period_start.strftime("%Y-%m-%d")
                        period_end = subscription.current_period_end.strftime("%Y-%m-%d")
                        html += f'<td style="padding: 8px;">{period_start} to {period_end}</td>'
                    else:
                        html += '<td style="padding: 8px;">-</td>'
                    html += "</tr>"

                html += "</tbody></table>"

            # Charges section (all payments including one-off and recurring)
            charges = customer.charges.all().order_by("-created")
            charge_count = charges.count()

            if charge_count > 0:
                html += f"<h4>All Payments ({charge_count})</h4>"
                html += '<table style="width: 100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += (
                    '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
                    "Amount</th>"
                )
                html += (
                    '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
                    "Type</th>"
                )
                html += (
                    '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
                    "Status</th>"
                )
                html += (
                    '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
                    "Date</th>"
                )
                html += (
                    '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">'
                    "Payment Method</th>"
                )
                html += "</tr></thead><tbody>"

                for charge in charges:
                    html += '<tr style="border-bottom: 1px solid #ddd;">'
                    html += f'<td style="padding: 8px;">${charge.amount}</td>'
                    charge_type = "recurring" if charge.invoice else "one-time"
                    html += f'<td style="padding: 8px;">{charge_type}</td>'
                    html += f'<td style="padding: 8px;">{charge.status}</td>'
                    created_str = charge.created.strftime("%Y-%m-%d %H:%M")
                    html += f'<td style="padding: 8px;">{created_str}</td>'

                    # Handle payment method - can be object or dict
                    payment_info = "-"
                    if charge.payment_method:
                        try:
                            card = charge.payment_method.card
                            if isinstance(card, dict):
                                brand = card.get("display_brand") or card.get("brand", "Card")
                                last4 = card.get("last4", "")
                                payment_info = f"{brand} {last4}"
                            elif card:
                                payment_info = f"{card.display_brand} {card.last4}"
                        except (AttributeError, TypeError):
                            pass

                    html += f'<td style="padding: 8px;">{payment_info}</td>'
                    html += "</tr>"

                html += "</tbody></table>"

            if subscription_count == 0 and charge_count == 0:
                html += "<p>No donations found</p>"

            html += "</div>"
            return mark_safe(html)
        except Exception as e:
            return mark_safe(
                f'<div style="color: red;">Error loading donation data: {str(e)}</div>'
            )

    donation_history.short_description = "Donation History"

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        else:
            return (
                "active_subscription",
                "discord_activity",
                "email_activity_sparkline",
                "apps_connected",
                "membership",
                "user",
                "mailjet_contact_id",
                "council_district_calculated",
                "email_history",
                "donation_history",
            )

    fieldsets = [
        (
            "Membership",
            {
                "fields": [
                    "membership",
                    "active_subscription",
                    "apps_connected",
                    "discord_activity",
                ]
            },
        ),
        (
            "Demographics",
            {"fields": ["user", "street_address", "zip_code", "council_district_calculated"]},
        ),
        (
            "Preferences",
            {"fields": ["newsletter_opt_in"]},
        ),
        (
            "Internal",
            {"fields": ["mailjet_contact_id"]},
        ),
        (
            "Donations",
            {"fields": ["donation_history"]},
        ),
        (
            "Email History",
            {"fields": ["email_activity_sparkline", "email_history"]},
        ),
    ]

    def save_model(self, request, obj, form, change):
        if change:
            original_obj = type(obj).objects.get(pk=obj.pk)
            original_value = getattr(original_obj, "location")
            obj.location = original_value
            form.cleaned_data["location"] = original_value

        super().save_model(request, obj, form, change)


@admin.action(description="Mark selected shirts as fulfilled")
def make_fulfilled(modeladmin, request, queryset):
    queryset.update(fulfilled=True)


@admin.action(description="Export Shipping Labels as PDF")
def export_shipping_labels(modeladmin, request, queryset):
    """
    Export 4x6 shipping labels for selected shirt orders.
    Groups orders by user/email and creates one label per recipient.
    """
    # Group orders by user/email
    orders_by_user = defaultdict(list)
    for order in queryset.select_related("user"):
        # Use email as the key to group orders
        key = (order.user.email, order.user.id)
        orders_by_user[key].append(order)

    # Create PDF
    buffer = BytesIO()
    # 4x6 inches label size
    label_width = 4 * rl_inch
    label_height = 6 * rl_inch

    c = canvas.Canvas(buffer, pagesize=(label_width, label_height))

    # Return address
    return_address = [
        "Philly Bike Action",
        "c/o Ee Durbin",
        "1239 S 8th Street",
        "Philadelphia, PA 19147",
    ]

    # Process each unique user/recipient
    for (email, user_id), orders in orders_by_user.items():
        # Get shipping details from the first order (all should be the same for same user)
        first_order = orders[0]

        # Top 1/3 - Return address
        y_position = label_height - 0.3 * rl_inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.25 * rl_inch, y_position, "FROM:")
        c.setFont("Helvetica", 9)
        for line in return_address:
            y_position -= 0.15 * rl_inch
            c.drawString(0.25 * rl_inch, y_position, line)

        # Separator line after return address
        y_position -= 0.2 * rl_inch
        c.line(0.25 * rl_inch, y_position, label_width - 0.25 * rl_inch, y_position)

        # Middle 1/3 - Shipping address
        y_position -= 0.3 * rl_inch
        c.setFont("Helvetica-Bold", 12)
        c.drawString(0.25 * rl_inch, y_position, "TO:")
        c.setFont("Helvetica-Bold", 11)

        # Build shipping address lines
        shipping_lines = []
        if first_order.shipping_name():
            shipping_lines.append(first_order.shipping_name())
        if first_order.shipping_line1():
            shipping_lines.append(first_order.shipping_line1())
        if first_order.shipping_line2():
            shipping_lines.append(first_order.shipping_line2())

        # City, State ZIP line
        city_state_zip = []
        if first_order.shipping_city():
            city_state_zip.append(first_order.shipping_city())
        if first_order.shipping_state():
            if city_state_zip:
                city_state_zip.append(f"{first_order.shipping_state()}")
            else:
                city_state_zip.append(first_order.shipping_state())
        if first_order.shipping_postal_code():
            city_state_zip.append(first_order.shipping_postal_code())

        if city_state_zip:
            # Handle city, state separately for proper formatting
            if first_order.shipping_city() and first_order.shipping_state():
                shipping_lines.append(
                    f"{first_order.shipping_city()}, {first_order.shipping_state()} "
                    f"{first_order.shipping_postal_code() or ''}".strip()
                )
            else:
                shipping_lines.append(" ".join(city_state_zip))

        for line in shipping_lines:
            y_position -= 0.18 * rl_inch
            c.drawString(0.25 * rl_inch, y_position, line)

        # Separator line after shipping address
        y_position -= 0.25 * rl_inch
        c.line(0.25 * rl_inch, y_position, label_width - 0.25 * rl_inch, y_position)

        # Bottom 1/3 - Items list
        y_position -= 0.3 * rl_inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.25 * rl_inch, y_position, "ITEMS:")
        c.setFont("Helvetica", 8)

        # List all items for this user
        for order in orders:
            y_position -= 0.15 * rl_inch

            # Build item description
            item_parts = []
            if order.get_product_type_display():
                item_parts.append(order.get_product_type_display())
            if order.get_fit_display():
                item_parts.append(order.get_fit_display())
            if order.get_size_display():
                item_parts.append(f"Size {order.get_size_display()}")
            if order.get_print_color_display():
                item_parts.append(f"{order.get_print_color_display()} print")

            item_text = " - ".join(item_parts)

            # Wrap text if too long
            if len(item_text) > 50:
                c.drawString(0.3 * rl_inch, y_position, "• " + item_text[:50])
                y_position -= 0.12 * rl_inch
                c.drawString(0.4 * rl_inch, y_position, item_text[50:])
            else:
                c.drawString(0.3 * rl_inch, y_position, "• " + item_text)

        # Create new page for next label
        c.showPage()

    # Save PDF
    c.save()

    # Create HTTP response
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="shipping_labels.pdf"'

    return response


@admin.action(description="Export Orders as CSV")
def csv_export(self, request, queryset):

    fields = [
        "product_type",
        "shipping_method",
        "shipping_name",
        "shipping_line1",
        "shipping_line2",
        "shipping_city",
        "shipping_state",
        "shipping_postal_code",
        "get_fit_display",
        "get_print_color_display",
        "get_size_display",
    ]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=shirt-orders.csv"
    writer = csv.writer(response)
    writer.writerow(fields)
    for obj in queryset:
        writer.writerow(
            [
                obj.get_product_type_display(),
                obj.shipping_method,
                obj.shipping_name(),
                obj.shipping_line1(),
                obj.shipping_line2(),
                obj.shipping_city(),
                obj.shipping_state(),
                obj.shipping_postal_code(),
                obj.get_fit_display(),
                obj.get_print_color_display(),
                obj.get_size_display(),
            ]
        )

    return response


class ShirtOrderAdmin(ReadOnlyLeafletGeoAdminMixin, admin.ModelAdmin):
    list_display = [
        "user",
        "product_type",
        "paid",
        "shipping_method",
        "fulfilled",
        "fit",
        "size",
        "print_color",
    ]
    list_filter = [
        "product_type",
        "paid",
        "shipping_method",
        "fulfilled",
        "fit",
        "size",
        "print_color",
    ]
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    autocomplete_fields = ("user",)
    readonly_fields = [
        "shipping_name",
        "shipping_line1",
        "shipping_line2",
        "shipping_city",
        "shipping_state",
        "shipping_postal_code",
    ]
    actions = [csv_export, make_fulfilled, export_shipping_labels]


admin.site.register(ShirtOrder, ShirtOrderAdmin)


class OrganizerProfileAdmin(ProfileAdmin):
    autocomplete_fields = []
    list_filter = [
        ProfileCompleteFilter,
        AppsConnectedFilter,
        GeolocatedFilter,
        OrganizerDistrictFilter,
        OrganizerRCOFilter,
    ]

    def has_module_permission(self, request):
        if request.user.is_authenticated:
            return request.user.profile.is_organizer
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        q_objects = Q()
        for district in request.user.profile.organized_districts.all():
            q_objects |= Q(location__within=district.mpoly)
        qs = qs.filter(q_objects)
        return qs


admin.site.register(Profile, ProfileAdmin)
organizer_admin.register(Profile, OrganizerProfileAdmin)


class UserAdmin(BaseUserAdmin):
    list_display = ["email", "first_name", "last_name", "is_staff", "is_superuser", "date_joined"]
    fieldsets = (("Profile", {"fields": ("profile",)}),) + BaseUserAdmin.fieldsets
    add_fieldsets = (("Profile", {"fields": ("profile",)}),) + BaseUserAdmin.add_fieldsets
    readonly_fields = ["profile"]


class OrganizerUserAdmin(UserAdmin):
    list_display = ["first_name", "last_name"]

    def has_module_permission(self, request):
        if request.user.is_authenticated:
            return request.user.profile.is_organizer
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        q_objects = Q()
        for district in request.user.profile.organized_districts.all():
            q_objects |= Q(profile__location__within=district.mpoly)
        qs = qs.filter(q_objects)
        return qs


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
organizer_admin.register(User, OrganizerUserAdmin)


class DoNotEmailAdmin(admin.ModelAdmin):
    list_display = ["email", "reason", "created_at"]
    list_filter = ["reason", "created_at"]
    search_fields = ["email"]
    readonly_fields = ["created_at"]


admin.site.register(DoNotEmail, DoNotEmailAdmin)
