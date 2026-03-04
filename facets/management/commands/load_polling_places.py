import json
import pathlib

from django.core.management.base import BaseCommand

from facets.models import Division


class Command(BaseCommand):
    help = "Load polling place data into Political Divisions from GeoJSON"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be updated without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        geojson_path = (
            pathlib.Path(__file__).parent.parent.parent / "data" / "polling_places.geojson"
        )

        with open(geojson_path) as f:
            data = json.load(f)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        updated_count = 0
        not_found_count = 0

        for feature in data["features"]:
            props = feature["properties"]
            ward_num = props["ward"]
            div_num = props["division"]
            name = f"Ward {ward_num} Division {div_num}"

            division = Division.objects.filter(name=name).first()
            if not division:
                self.stdout.write(self.style.WARNING(f"Division not found: {name}"))
                not_found_count += 1
                continue

            if dry_run:
                self.stdout.write(f"Would update {name} with {props['placename']}")
                updated_count += 1
                continue

            division.polling_place_name = props.get("placename", "")
            division.polling_place_address = props.get("street_address", "")
            division.polling_place_zip = props.get("zip_code", "")
            division.polling_place_accessibility = props.get("accessibility_code", "")
            division.polling_place_parking = props.get("parking_code", "")
            division.save(
                update_fields=[
                    "polling_place_name",
                    "polling_place_address",
                    "polling_place_zip",
                    "polling_place_accessibility",
                    "polling_place_parking",
                ]
            )
            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Done: {updated_count} updated, {not_found_count} not found")
        )
