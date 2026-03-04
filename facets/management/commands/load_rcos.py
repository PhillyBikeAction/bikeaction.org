import json
import pathlib

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand

from facets.models import RegisteredCommunityOrganization


class Command(BaseCommand):
    help = "Load or update Registered Community Organizations from GeoJSON"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be created or updated without making changes",
        )
        parser.add_argument(
            "--delete-stale",
            action="store_true",
            help="Delete RCOs not present in the GeoJSON file",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        delete_stale = options["delete_stale"]
        geojson_path = pathlib.Path(__file__).parent.parent.parent / "data" / "Zoning_RCO.geojson"

        with open(geojson_path) as f:
            data = json.load(f)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        created_count = 0
        updated_count = 0
        file_names = set()

        for feature in data["features"]:
            props = feature["properties"]
            name = props["organization_name"]
            file_names.add(name)

            lni_id = props.get("lni_id")
            existing = RegisteredCommunityOrganization.objects.filter(name=name).first()

            if existing and existing.properties.get("lni_id") != lni_id:
                self.stdout.write(
                    self.style.WARNING(
                        f"lni_id mismatch for {name}: "
                        f"db={existing.properties.get('lni_id')}, file={lni_id}"
                    )
                )

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

            rco, created = RegisteredCommunityOrganization.objects.update_or_create(
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
            self.stdout.write(f"{action} {rco.name}")

        deleted_count = 0
        if delete_stale:
            stale = RegisteredCommunityOrganization.objects.exclude(name__in=file_names)
            for rco in stale:
                if dry_run:
                    self.stdout.write(f"Would delete {rco.name}")
                else:
                    self.stdout.write(f"Deleted {rco.name}")
                deleted_count += 1
            if not dry_run:
                stale.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_count} created, {updated_count} updated, {deleted_count} deleted"
            )
        )
