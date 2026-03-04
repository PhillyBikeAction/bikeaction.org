import json
import pathlib

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand

from facets.models import Division, Ward


class Command(BaseCommand):
    help = "Load or update Political Divisions from GeoJSON"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be created or updated without making changes",
        )
        parser.add_argument(
            "--delete-stale",
            action="store_true",
            help="Delete Divisions not present in the GeoJSON file",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        delete_stale = options["delete_stale"]
        geojson_path = (
            pathlib.Path(__file__).parent.parent.parent / "data" / "Political_Divisions.geojson"
        )

        with open(geojson_path) as f:
            data = json.load(f)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        wards = {}
        for w in Ward.objects.all():
            ward_num = w.properties.get("ward_num") or w.properties.get("ward_number")
            if ward_num is not None:
                wards[int(ward_num)] = w
        if not wards and not dry_run:
            self.stdout.write(self.style.ERROR("No Wards found. Run load_wards first."))
            return

        created_count = 0
        updated_count = 0
        file_names = set()

        for feature in data["features"]:
            props = feature["properties"]
            division_num = props["DIVISION_NUM"]
            ward_num = division_num[:2]
            div_num = division_num[2:]
            name = f"Ward {int(ward_num)} Division {int(div_num)}"
            file_names.add(name)

            ward = wards.get(int(ward_num))
            if not ward and not dry_run:
                self.stdout.write(
                    self.style.WARNING(f"No ward found for ward_num={ward_num}, skipping {name}")
                )
                continue

            existing = Division.objects.filter(name=name).first()

            if dry_run:
                action = "Would update" if existing else "Would create"
                if existing:
                    updated_count += 1
                else:
                    created_count += 1
                self.stdout.write(f"{action} {name} (Political Ward {int(ward_num)})")
                continue

            geojson = json.dumps(feature["geometry"])
            geos_geom = GEOSGeometry(geojson)

            if geos_geom.geom_type == "Polygon":
                geos_geom = MultiPolygon(geos_geom)

            division, created = Division.objects.update_or_create(
                name=name,
                defaults={
                    "mpoly": geos_geom,
                    "properties": props,
                    "ward": ward,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} {division.name}")

        deleted_count = 0
        if delete_stale:
            stale = Division.objects.exclude(name__in=file_names)
            for division in stale:
                if dry_run:
                    self.stdout.write(f"Would delete {division.name}")
                else:
                    self.stdout.write(f"Deleted {division.name}")
                deleted_count += 1
            if not dry_run:
                stale.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_count} created, {updated_count} updated, {deleted_count} deleted"
            )
        )
