release: uv run python manage.py migrate
web: uv run python -m gunicorn -c gunicorn.conf.py pbaabp.asgi --bind :$PORT
worker: uv run python -m celery -A pbaabp worker -c 1 --beat -l INFO
discordworker: uv run python manage.py run_discord
