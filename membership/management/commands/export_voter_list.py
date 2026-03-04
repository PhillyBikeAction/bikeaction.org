import csv
import re
import uuid
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from facets.models import District, ZipCode
from membership.models import Membership

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Export a voter list of members as of a given date. "
        "Users are considered members if they have: "
        "(1) an active Membership record, "
        "(2) Discord activity within 30 days, or "
        "(3) an active Stripe subscription."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "as_of_date",
            type=str,
            help="Date to check membership status (YYYY-MM-DD format)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="voter_list.csv",
            help="Output CSV file path (default: voter_list.csv)",
        )

    def handle(self, *args, **options):
        # Parse the date
        as_of_date_str = options["as_of_date"]

        try:
            # Parse as date first
            date_obj = datetime.strptime(as_of_date_str, "%Y-%m-%d").date()
            # Create datetime bounds for the target date in UTC
            # This is needed because Stripe invoice timestamps are in UTC
            import pytz

            # Start of day in UTC
            day_start_utc = datetime.combine(date_obj, datetime.min.time()).replace(tzinfo=pytz.UTC)
            # End of day in UTC
            day_end_utc = datetime.combine(date_obj, datetime.max.time()).replace(tzinfo=pytz.UTC)
        except ValueError:
            self.stderr.write(
                self.style.ERROR(f"Invalid date format: {as_of_date_str}. Use YYYY-MM-DD")
            )
            return

        output_file = options["output"]

        # Calculate Discord activity window (30 days before target date)
        # Use date arithmetic to avoid timezone conversion issues
        discord_activity_start_date = date_obj - timedelta(days=30)

        # Build query to find all users who are members as of the given date
        # A user is a member if they meet ANY of these criteria:
        # 1. Have an explicit Membership record active on the target date
        # 2. Have Discord activity within 30 days before the target date
        # 3. Have a Stripe subscription active on the target date

        # Membership active on target date:
        # - membership starts before or on end of day
        # - AND (membership has no end_date OR end_date >= start of day)
        membership_record_query = Q(memberships__start_date__lte=day_end_utc) & (
            Q(memberships__end_date__isnull=True) | Q(memberships__end_date__gte=day_start_utc)
        )

        # Discord activity within 30 days before target date
        # User must have BOTH a linked Discord account AND recent activity
        # Use date comparison since DiscordActivity.date is a DateField
        discord_activity_query = Q(socialaccount__provider="discord") & Q(
            profile__discord_activity__date__gte=discord_activity_start_date,
            profile__discord_activity__date__lte=date_obj,
        )

        # Stripe subscription active on target date
        # We need to check BOTH:
        # 1. Historical invoices (for past billing periods)
        # 2. Current subscription periods (for ongoing subscriptions)
        # This is because invoices are only created after a billing period ends
        stripe_invoice_query = Q(
            djstripe_customers__subscriptions__invoices__period_start__lte=day_end_utc,
            djstripe_customers__subscriptions__invoices__period_end__gte=day_start_utc,
            djstripe_customers__subscriptions__invoices__status="paid",
        )
        stripe_current_period_query = Q(
            djstripe_customers__subscriptions__current_period_start__lte=day_end_utc,
            djstripe_customers__subscriptions__current_period_end__gte=day_start_utc,
        )
        stripe_subscription_query = stripe_invoice_query | stripe_current_period_query

        # Debug: Count each criteria separately
        membership_users = User.objects.filter(membership_record_query).distinct().count()
        discord_users = User.objects.filter(discord_activity_query).distinct().count()
        stripe_users = User.objects.filter(stripe_subscription_query).distinct().count()

        # Debug Membership records
        total_memberships = Membership.objects.count()
        active_on_date = Membership.objects.filter(start_date__lte=day_end_utc).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=day_start_utc)
        )
        self.stdout.write(self.style.WARNING("\nMembership Debug Info:"))
        self.stdout.write(f"  - Total Membership records in DB: {total_memberships}")
        self.stdout.write(f"  - Active on {date_obj}: {active_on_date.count()}")
        if active_on_date.exists():
            self.stdout.write("  - Sample active memberships:")
            for mem in active_on_date[:5]:
                self.stdout.write(
                    f"    * User {mem.user.email}: {mem.start_date} to "
                    f"{mem.end_date or 'ongoing'} ({mem.kind})"
                )

        # Debug Discord activity
        from profiles.models import DiscordActivity

        total_discord_activities = DiscordActivity.objects.count()
        activities_in_window = DiscordActivity.objects.filter(
            date__gte=discord_activity_start_date,
            date__lte=date_obj,
        ).count()
        unique_discord_users = (
            DiscordActivity.objects.filter(
                date__gte=discord_activity_start_date,
                date__lte=date_obj,
            )
            .values("profile__user")
            .distinct()
            .count()
        )

        self.stdout.write(self.style.WARNING("\nDiscord Debug Info:"))
        self.stdout.write(f"  - Total Discord activities in DB: {total_discord_activities}")
        self.stdout.write(
            f"  - Activities in window ({discord_activity_start_date} to {date_obj}): "
            f"{activities_in_window}"
        )
        self.stdout.write(f"  - Unique users with activity: {unique_discord_users}")

        # Debug Stripe subscriptions
        from djstripe.models import Invoice, Subscription

        total_subs = Subscription.objects.count()
        total_invoices = Invoice.objects.count()
        invoices_covering_date = Invoice.objects.filter(
            period_start__lte=day_end_utc,
            period_end__gte=day_start_utc,
            status="paid",
        ).count()
        unique_subs_with_invoices = (
            Invoice.objects.filter(
                period_start__lte=day_end_utc,
                period_end__gte=day_start_utc,
                status="paid",
            )
            .values("subscription_id")
            .distinct()
            .count()
        )
        self.stdout.write(self.style.WARNING("\nStripe Debug Info:"))
        self.stdout.write(f"  - Total Subscriptions in DB: {total_subs}")
        self.stdout.write(f"  - Total Invoices in DB: {total_invoices}")
        self.stdout.write(f"  - Paid invoices covering {date_obj}: {invoices_covering_date}")
        self.stdout.write(
            f"  - Unique subscriptions with paid invoices on {date_obj}: "
            f"{unique_subs_with_invoices}"
        )

        # Combine all three criteria with OR
        members_query = membership_record_query | discord_activity_query | stripe_subscription_query

        # Get all users matching the criteria
        members = User.objects.filter(members_query).select_related("profile").distinct()

        self.stdout.write(f"\nTotal users in database: {User.objects.count()}")
        self.stdout.write(f"Members as of {date_obj}: {members.count()}")
        self.stdout.write(f"  - Via Membership records: {membership_users}")
        self.stdout.write(f"  - Via Discord activity: {discord_users}")
        self.stdout.write(f"  - Via Stripe subscriptions: {stripe_users}")

        # Check for users without profiles
        users_without_profiles = members.filter(profile__isnull=True).count()
        if users_without_profiles > 0:
            self.stdout.write(
                self.style.WARNING(f"  - {users_without_profiles} users excluded (no profile)")
            )

        # Prepare data for CSV export
        voter_data = []

        for user in members:
            email = user.email
            district_number = None

            # Get the district from the user's profile
            if hasattr(user, "profile") and user.profile:
                profile = user.profile

                # First try to get district from location (geocoded address)
                district_obj = profile.district
                if district_obj:
                    # Extract district number from name (e.g., "District 5" -> "5")
                    match = re.search(r"\d+", district_obj.name)
                    if match:
                        district_number = match.group()

                # If no district from location, try to infer from zip code
                if not district_number and profile.zip_code:
                    zip_code_str = profile.zip_code.strip()
                    # Look up the ZipCode facet
                    try:
                        zip_facet = ZipCode.objects.get(name=zip_code_str)
                        # Find districts that intersect with this zip code
                        # Use the centroid of the zip to find the most likely district
                        districts = District.objects.filter(mpoly__intersects=zip_facet.mpoly)
                        if districts.exists():
                            # If multiple districts, use the one containing the centroid
                            centroid = zip_facet.mpoly.centroid
                            district_from_centroid = districts.filter(
                                mpoly__contains=centroid
                            ).first()
                            if district_from_centroid:
                                district_obj = district_from_centroid
                            else:
                                # Fall back to first intersecting district
                                district_obj = districts.first()

                            # Extract district number
                            match = re.search(r"\d+", district_obj.name)
                            if match:
                                district_number = match.group()
                    except ZipCode.DoesNotExist:
                        # Zip code not in database, continue without district
                        pass

            # Password is the literal string "password,"
            password = "password,"

            # Generate a UUID for the unique_id
            user_uuid = str(uuid.uuid4())

            # Format unique_id as "dN-{UUID}" where N is the district number
            if district_number:
                unique_id = f"d{district_number}-{user_uuid}"
            else:
                # If no district, use d0
                unique_id = f"d0-{user_uuid}"

            # Get full name
            full_name = user.get_full_name() or ""

            voter_data.append(
                {
                    "password": password,
                    "unique_id": unique_id,
                    "email": email,
                    "full_name": full_name,
                }
            )

        # Write to CSV
        with open(output_file, "w", newline="") as csvfile:
            fieldnames = ["password", "unique_id", "email", "full_name"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            writer.writerows(voter_data)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully exported {len(voter_data)} members to {output_file}")
        )
        self.stdout.write(self.style.SUCCESS(f"Membership as of: {date_obj.strftime('%Y-%m-%d')}"))

        # Summary statistics
        with_district = sum(1 for row in voter_data if not row["unique_id"].startswith("d0-"))
        without_district = len(voter_data) - with_district

        self.stdout.write(self.style.SUCCESS(f"Members with district: {with_district}"))
        if without_district > 0:
            self.stdout.write(self.style.WARNING(f"Members without district: {without_district}"))
