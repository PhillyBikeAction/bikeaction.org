from time import monotonic

from django.core.management.base import BaseCommand

from profiles.tasks import sync_connected_roles


class Command(BaseCommand):
    help = "Update roles for all connected discord auths"

    def handle(self, *args, **kwargs):
        started = last_report = monotonic()

        def report_progress(updated, skipped):
            nonlocal last_report
            now = monotonic()
            processed = updated + skipped
            if processed == 1 or processed % 100 == 0 or now - last_report >= 10:
                self.stdout.write(
                    f"Processed {processed} accounts: {updated} updated, {skipped} skipped "
                    f"({now - started:.0f}s elapsed)."
                )
                self.stdout.flush()
                last_report = now

        self.stdout.write("Syncing connected Discord roles...")
        self.stdout.flush()
        result = sync_connected_roles(progress=report_progress)
        self.stdout.write(
            self.style.SUCCESS(
                f"Connected role sync complete: {result['updated']} updated, "
                f"{result['skipped']} skipped."
            )
        )
