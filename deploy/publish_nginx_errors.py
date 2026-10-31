"""Publish standalone error pages to the directory shared with host nginx."""

import argparse
import os
from pathlib import Path
import tempfile


SOURCE = Path(__file__).resolve().parent.parent / "nginx-errors"
DESTINATION = Path("/nginx-error-pages")
FILENAMES = tuple(f"{code}-error.html" for code in (400, 404, 500, 502))


def publish(check_only=False):
    if not DESTINATION.is_mount():
        raise SystemExit(
            "/nginx-error-pages must be a Dokku storage mount. "
            "See README.md: Static nginx error pages."
        )

    # Read all sources before touching the currently served files.
    pages = {name: (SOURCE / name).read_bytes() for name in FILENAMES}
    for name, contents in pages.items():
        if not contents.startswith(b"<!doctype html>"):
            raise SystemExit(f"Invalid error page: {name}")

    # Creating a temporary file also checks write access in --check mode.
    for name, contents in pages.items():
        with tempfile.NamedTemporaryFile(dir=DESTINATION, delete=False) as output:
            temporary = Path(output.name)
            try:
                if not check_only:
                    output.write(contents)
                    output.flush()
                    os.fchmod(output.fileno(), 0o644)
                    os.fsync(output.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            if not check_only:
                # Readers see a complete old or new page, never a partial write.
                temporary.replace(DESTINATION / name)
        finally:
            temporary.unlink(missing_ok=True)

    print("Nginx error-page mount verified." if check_only else "Nginx error pages published.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without replacing pages")
    publish(check_only=parser.parse_args().check)
