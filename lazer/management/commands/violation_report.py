import json
from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from lazer.models import ViolationReport
from lazer.reports import filter_violation_reports, generate_html_report


class Command(BaseCommand):
    help = "Generate a report of violations within a GeoJSON polygon, optionally comparing before/after a date"

    generate_html_report = staticmethod(generate_html_report)

    def add_arguments(self, parser):
        parser.add_argument("--start-date", help="Include captures from this date (YYYY-MM-DD)")
        parser.add_argument("--end-date", help="Include captures through this date (YYYY-MM-DD)")
        parser.add_argument(
            "--geojson",
            type=str,
            help="GeoJSON string or file path containing the polygon",
        )
        parser.add_argument(
            "--street-name",
            type=str,
            help="Street name to filter by (e.g., 'S 13TH ST')",
        )
        parser.add_argument(
            "--block-range",
            type=str,
            help="Block number range (e.g., '100-300' or '100')",
        )
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Comparison date in YYYY-MM-DD format (optional; enables before/after analysis)",
        )
        parser.add_argument(
            "--timezone",
            type=str,
            default="America/New_York",
            help="Timezone for date comparison (default: America/New_York)",
        )
        parser.add_argument(
            "--html",
            type=str,
            help="Generate HTML report and save to this file path",
        )

    def handle(self, *args, **options):
        # Check that either geojson or street-name is provided
        geojson_input = options.get("geojson")
        street_name = options.get("street_name")
        block_range = options.get("block_range")

        if not geojson_input and not street_name:
            self.stdout.write(
                self.style.ERROR("Either --geojson or --street-name must be provided")
            )
            return

        # Initialize variables
        polygon = None
        geojson_data = None
        filter_mode = None

        if geojson_input:
            # Parse GeoJSON
            filter_mode = "geojson"
            try:
                # Try to parse as JSON string first
                geojson_data = json.loads(geojson_input)
            except json.JSONDecodeError:
                # If that fails, try to read as file path
                try:
                    with open(geojson_input, "r") as f:
                        geojson_data = json.load(f)
                except FileNotFoundError:
                    self.stdout.write(
                        self.style.ERROR(f"Could not parse GeoJSON or find file: {geojson_input}")
                    )
                    return

            # Extract the polygon geometry
            if geojson_data.get("type") == "FeatureCollection":
                # Get the first feature's geometry
                geometry = geojson_data["features"][0]["geometry"]
            elif geojson_data.get("type") == "Feature":
                geometry = geojson_data["geometry"]
            else:
                geometry = geojson_data

            # Convert to GEOSGeometry
            polygon = GEOSGeometry(json.dumps(geometry))
        else:
            # Street-based filtering
            filter_mode = "street"

        # Parse the comparison date (optional)
        try:
            start_date = (
                datetime.strptime(options["start_date"], "%Y-%m-%d").date()
                if options.get("start_date")
                else None
            )
            end_date = (
                datetime.strptime(options["end_date"], "%Y-%m-%d").date()
                if options.get("end_date")
                else None
            )
        except ValueError as error:
            raise CommandError("Capture dates must use YYYY-MM-DD.") from error
        if start_date and end_date and start_date > end_date:
            raise CommandError("End date must be on or after start date.")
        if end_date and end_date.year == 9999:
            raise CommandError("End date must be before the year 9999.")
        comparison_date_str = options["date"]
        tz = ZoneInfo(options["timezone"])
        if comparison_date_str:
            comparison_date = datetime.strptime(comparison_date_str, "%Y-%m-%d").replace(tzinfo=tz)
        else:
            comparison_date = None

        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}"))
        self.stdout.write(self.style.SUCCESS("Violation Report for Area"))
        self.stdout.write(self.style.SUCCESS(f"{'=' * 60}\n"))

        violations_in_area = filter_violation_reports(
            ViolationReport.objects.all(),
            polygon=polygon,
            street_name=street_name,
            block_range=block_range,
            start_date=start_date,
            end_date=end_date,
            timezone_name=options["timezone"],
        )

        total_count = violations_in_area.count()
        if start_date or end_date:
            self.stdout.write(
                f"Capture dates: {start_date or 'Beginning'} through {end_date or 'Present'} "
                f"({options['timezone']})\n"
            )

        # Display filter criteria
        if filter_mode == "geojson":
            self.stdout.write(f"Polygon coordinates: {polygon.coords}\n")
        else:
            self.stdout.write(f"Street name: {street_name}\n")
            if block_range:
                self.stdout.write(f"Block range: {block_range}\n")

        if comparison_date:
            self.stdout.write(f"Comparison date: {comparison_date_str}\n")
        self.stdout.write(f"Total violations in area: {total_count}\n")

        if comparison_date:
            # Split by date
            before = violations_in_area.filter(submission__captured_at__lt=comparison_date)
            after = violations_in_area.filter(submission__captured_at__gte=comparison_date)

            before_count = before.count()
            after_count = after.count()

            # Calculate date ranges for averages
            if total_count > 0:
                min_date = violations_in_area.earliest(
                    "submission__captured_at"
                ).submission.captured_at.date()
                max_date = violations_in_area.latest(
                    "submission__captured_at"
                ).submission.captured_at.date()
                comparison_date_only = comparison_date.date()

                days_before = (comparison_date_only - min_date).days
                days_after = (
                    max_date - comparison_date_only
                ).days + 1  # Include the comparison date in after

                avg_before = before_count / days_before if days_before > 0 else 0
                avg_after = after_count / days_after if days_after > 0 else 0
            else:
                days_before = 0
                days_after = 0
                avg_before = 0
                avg_after = 0

            self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}"))
            self.stdout.write(self.style.SUCCESS(f"BEFORE {comparison_date_str}"))
            self.stdout.write(self.style.SUCCESS(f"{'=' * 60}\n"))
            self.stdout.write(f"Count: {before_count}\n")
            self.stdout.write(f"Days: {days_before}\n")
            self.stdout.write(f"Average per day: {avg_before:.2f}\n")

            if before_count > 0:
                earliest = before.earliest("submission__captured_at")
                latest = before.latest("submission__captured_at")
                self.stdout.write(f"First violation: {earliest.submission.captured_at}")
                self.stdout.write(f"Last violation:  {latest.submission.captured_at}\n")

                # Breakdown by violation type
                self.stdout.write("Breakdown by violation type:")
                for report in (
                    before.values("violation_observed")
                    .annotate(count=Count("id"))
                    .order_by("-count")
                ):
                    violation_type = report["violation_observed"] or "Unknown"
                    count = report["count"]
                    self.stdout.write(f"  - {violation_type}: {count}")

            self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}"))
            self.stdout.write(self.style.SUCCESS(f"AFTER {comparison_date_str}"))
            self.stdout.write(self.style.SUCCESS(f"{'=' * 60}\n"))
            self.stdout.write(f"Count: {after_count}\n")
            self.stdout.write(f"Days: {days_after}\n")
            self.stdout.write(f"Average per day: {avg_after:.2f}\n")

            if after_count > 0:
                earliest = after.earliest("submission__captured_at")
                latest = after.latest("submission__captured_at")
                self.stdout.write(f"First violation: {earliest.submission.captured_at}")
                self.stdout.write(f"Last violation:  {latest.submission.captured_at}\n")

                # Breakdown by violation type
                self.stdout.write("Breakdown by violation type:")
                for report in (
                    after.values("violation_observed")
                    .annotate(count=Count("id"))
                    .order_by("-count")
                ):
                    violation_type = report["violation_observed"] or "Unknown"
                    count = report["count"]
                    self.stdout.write(f"  - {violation_type}: {count}")

            # Calculate change
            self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}"))
            self.stdout.write(self.style.SUCCESS("CHANGE"))
            self.stdout.write(self.style.SUCCESS(f"{'=' * 60}\n"))

            if before_count > 0:
                change = after_count - before_count
                percent_change = (change / before_count) * 100
                avg_change = avg_after - avg_before
                avg_percent_change = (avg_change / avg_before * 100) if avg_before > 0 else 0

                self.stdout.write(f"Absolute change (total): {change:+d}")
                self.stdout.write(f"Percent change (total): {percent_change:+.1f}%\n")
                self.stdout.write(f"Change in average per day: {avg_change:+.2f}")
                self.stdout.write(f"Percent change in average: {avg_percent_change:+.1f}%\n")
            else:
                self.stdout.write("No violations before comparison date to calculate change.\n")
        else:
            before_count = 0
            after_count = total_count

            # Breakdown by violation type
            if total_count > 0:
                self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}"))
                self.stdout.write(self.style.SUCCESS("VIOLATION TYPE BREAKDOWN"))
                self.stdout.write(self.style.SUCCESS(f"{'=' * 60}\n"))

                for report in (
                    violations_in_area.values("violation_observed")
                    .annotate(count=Count("id"))
                    .order_by("-count")
                ):
                    violation_type = report["violation_observed"] or "Unknown"
                    count = report["count"]
                    self.stdout.write(f"  - {violation_type}: {count}")

        # List all violations with details
        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}"))
        self.stdout.write(self.style.SUCCESS("ALL VIOLATIONS (chronological)"))
        self.stdout.write(self.style.SUCCESS(f"{'=' * 60}\n"))

        for i, report in enumerate(violations_in_area, 1):
            if comparison_date:
                period = "BEFORE" if report.submission.captured_at < comparison_date else "AFTER"
                self.stdout.write(
                    f"{i}. [{period}] {report.submission.captured_at} - "
                    f"Lat: {report.submission.location.y:.6f}, "
                    f"Lon: {report.submission.location.x:.6f}"
                )
            else:
                self.stdout.write(
                    f"{i}. {report.submission.captured_at} - "
                    f"Lat: {report.submission.location.y:.6f}, "
                    f"Lon: {report.submission.location.x:.6f}"
                )
            self.stdout.write(f"   Type: {report.violation_observed}")
            self.stdout.write(f"   Location: {report.block_number} {report.street_name}")

        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}\n"))

        # Generate HTML report if requested
        html_path = options.get("html")
        if html_path:
            html_content = self.generate_html_report(
                violations_in_area,
                polygon,
                comparison_date,
                comparison_date_str,
                before_count,
                after_count,
                geojson_data,
                filter_mode,
                street_name,
                block_range,
                start_date=start_date,
                end_date=end_date,
                timezone_name=options["timezone"],
            )

            with open(html_path, "w") as f:
                f.write(html_content)

            self.stdout.write(self.style.SUCCESS(f"\nHTML report generated: {html_path}"))
        elif filter_mode == "street" and street_name:
            # Auto-generate filename for street mode
            import re

            # Clean street name for filename
            clean_street = re.sub(r"[^\w\s-]", "", street_name).strip().replace(" ", "_")
            clean_block = (
                re.sub(r"[^\w\s-]", "", block_range).replace("-", "_") if block_range else "all"
            )
            auto_filename = f"violation_report_{clean_street}_{clean_block}.html"

            html_content = self.generate_html_report(
                violations_in_area,
                polygon,
                comparison_date,
                comparison_date_str,
                before_count,
                after_count,
                geojson_data,
                filter_mode,
                street_name,
                block_range,
                start_date=start_date,
                end_date=end_date,
                timezone_name=options["timezone"],
            )

            with open(auto_filename, "w") as f:
                f.write(html_content)

            self.stdout.write(self.style.SUCCESS(f"\nHTML report generated: {auto_filename}"))
