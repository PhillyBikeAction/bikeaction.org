import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count

from lazer.models import LazerWrapped, ViolationReport
from lazer.views import calculate_wrapped_stats

User = get_user_model()


class Command(BaseCommand):
    help = "Generate Lazer Vision Wrapped for all users who used it more than once"

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=datetime.datetime.now().year,
            help="Year to generate wrapped for (default: current year)",
        )
        parser.add_argument(
            "--min-reports",
            type=int,
            default=1,
            help="Minimum number of submitted reports required (default: 1)",
        )
        parser.add_argument(
            "--regenerate",
            action="store_true",
            help="Regenerate wrapped even if it already exists",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        year = options["year"]
        min_reports = options["min_reports"]
        regenerate = options["regenerate"]
        dry_run = options["dry_run"]

        self.stdout.write(f"Generating Lazer Vision Wrapped for {year}")
        self.stdout.write(f"Minimum reports required: {min_reports}")

        # Find users with at least min_reports submitted reports in the given year
        eligible_users = (
            ViolationReport.objects.filter(
                submitted__isnull=False,
                submission__captured_at__year=year,
                submission__created_by__isnull=False,
            )
            .values("submission__created_by")
            .annotate(report_count=Count("id"))
            .filter(report_count__gte=min_reports)
            .order_by("-report_count")
        )

        user_ids = [u["submission__created_by"] for u in eligible_users]
        users = User.objects.filter(id__in=user_ids)
        user_map = {u.id: u for u in users}

        self.stdout.write(f"Found {len(eligible_users)} eligible users\n")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for user_data in eligible_users:
            user_id = user_data["submission__created_by"]
            report_count = user_data["report_count"]
            user = user_map.get(user_id)

            if not user:
                continue

            # Check if wrapped already exists
            existing = LazerWrapped.objects.filter(user=user, year=year).first()

            if existing and not regenerate:
                self.stdout.write(f"  SKIP: {user.email} ({report_count} reports) - already exists")
                skipped_count += 1
                continue

            if dry_run:
                action = "UPDATE" if existing else "CREATE"
                self.stdout.write(f"  {action}: {user.email} ({report_count} reports)")
                if existing:
                    updated_count += 1
                else:
                    created_count += 1
                continue

            # Calculate stats
            stats = calculate_wrapped_stats(user, year)
            if stats is None:
                self.stdout.write(self.style.WARNING(f"  WARN: {user.email} - no stats calculated"))
                continue

            if existing:
                # Update existing wrapped
                existing.total_submissions = stats["total_submissions"]
                existing.total_reports = stats["total_reports"]
                existing.violations_by_type = stats["violations_by_type"]
                existing.top_streets = stats["top_streets"]
                existing.top_zip_codes = stats["top_zip_codes"]
                existing.reports_by_month = stats["reports_by_month"]
                existing.first_report_date = stats["first_report_date"]
                existing.longest_streak = stats["longest_streak"]
                existing.longest_streak_start = stats["longest_streak_start"]
                existing.longest_streak_end = stats["longest_streak_end"]
                existing.longest_streak_reports = stats["longest_streak_reports"]
                existing.top_day_date = stats["top_day_date"]
                existing.top_day_count = stats["top_day_count"]
                existing.top_user_vehicles = stats["top_user_vehicles"]
                existing.top_community_vehicles = stats["top_community_vehicles"]
                existing.rank = stats["rank"]
                existing.total_users = stats["total_users"]
                existing.percentile = stats["percentile"]
                existing.avg_reports = stats["avg_reports"]
                existing.total_community_reports = stats["total_community_reports"]
                existing.percent_of_total = stats["percent_of_total"]
                existing.save()
                self.stdout.write(
                    self.style.SUCCESS(f"  UPDATE: {user.email} ({report_count} reports)")
                )
                updated_count += 1
            else:
                # Create new wrapped
                LazerWrapped.objects.create(
                    user=user,
                    year=year,
                    total_submissions=stats["total_submissions"],
                    total_reports=stats["total_reports"],
                    violations_by_type=stats["violations_by_type"],
                    top_streets=stats["top_streets"],
                    top_zip_codes=stats["top_zip_codes"],
                    reports_by_month=stats["reports_by_month"],
                    first_report_date=stats["first_report_date"],
                    longest_streak=stats["longest_streak"],
                    longest_streak_start=stats["longest_streak_start"],
                    longest_streak_end=stats["longest_streak_end"],
                    longest_streak_reports=stats["longest_streak_reports"],
                    top_day_date=stats["top_day_date"],
                    top_day_count=stats["top_day_count"],
                    top_user_vehicles=stats["top_user_vehicles"],
                    top_community_vehicles=stats["top_community_vehicles"],
                    rank=stats["rank"],
                    total_users=stats["total_users"],
                    percentile=stats["percentile"],
                    avg_reports=stats["avg_reports"],
                    total_community_reports=stats["total_community_reports"],
                    percent_of_total=stats["percent_of_total"],
                )
                self.stdout.write(
                    self.style.SUCCESS(f"  CREATE: {user.email} ({report_count} reports)")
                )
                created_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Summary:"))
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n(Dry run - no changes made)"))
