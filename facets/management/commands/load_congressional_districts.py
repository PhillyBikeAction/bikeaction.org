import json
import pathlib

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand

from facets.models import CongressionalDistrict


class Command(BaseCommand):
    help = "Load or update Congressional Districts from GeoJSON"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be created or updated without making changes",
        )
        parser.add_argument(
            "--delete-stale",
            action="store_true",
            help="Delete Congressional Districts not present in the GeoJSON file",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        delete_stale = options["delete_stale"]
        geojson_path = (
            pathlib.Path(__file__).parent.parent.parent / "data" / "PaCongressional2024_03.geojson"
        )

        with open(geojson_path) as f:
            data = json.load(f)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        created_count = 0
        updated_count = 0
        file_names = set()

        for feature in data["features"]:
            props = feature["properties"]
            leg_district = props["LEG_DISTRI"]
            name = f"Legislative District {leg_district}"
            file_names.add(name)

            existing = CongressionalDistrict.objects.filter(name=name).first()

            if dry_run:
                action = "Would update" if existing else "Would create"
                if existing:
                    updated_count += 1
                else:
                    created_count += 1
                self.stdout.write(f"{action} {name}")
                continue

            geojson = json.dumps(feature["geometry"])
            geos_geom = GEOSGeometry(geojson)

            if geos_geom.geom_type == "Polygon":
                geos_geom = MultiPolygon(geos_geom)

            district, created = CongressionalDistrict.objects.update_or_create(
                name=name,
                defaults={
                    "mpoly": geos_geom,
                    "properties": props,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} {district.name}")

        deleted_count = 0
        if delete_stale:
            stale = CongressionalDistrict.objects.exclude(name__in=file_names)
            for district in stale:
                if dry_run:
                    self.stdout.write(f"Would delete {district.name}")
                else:
                    self.stdout.write(f"Deleted {district.name}")
                deleted_count += 1
            if not dry_run:
                stale.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_count} created, {updated_count} updated, {deleted_count} deleted"
            )
        )
