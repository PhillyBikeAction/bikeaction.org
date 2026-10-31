#!/bin/sh
set -eu

# Fail before migrations if the host's nginx error-page mount is missing.
python deploy/publish_nginx_errors.py --check
uv run python manage.py migrate
python deploy/publish_nginx_errors.py
