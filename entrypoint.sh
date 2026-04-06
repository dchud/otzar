#!/bin/sh
set -e

# Run migrations (volume is mounted, so DB is accessible)
uv run python manage.py migrate --noinput

# Start gunicorn
exec uv run gunicorn otzar.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
