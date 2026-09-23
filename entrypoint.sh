#!/bin/sh
set -e

# Run migrations (volume is mounted, so DB is accessible)
uv run python manage.py migrate --noinput

# Threads rather than sync workers: OCR and the SRU cascade both run
# inside the request and can each hold it for tens of seconds, and with
# two sync workers two such requests would stall every other page.
#
# --forwarded-allow-ips names the proxy whose X-Forwarded-* headers
# gunicorn passes through to Django. gunicorn's default, 127.0.0.1, is
# the proxy only when both share a network namespace; with the proxy on
# the host and gunicorn in a container, requests arrive from the Docker
# bridge, so the deployment sets FORWARDED_ALLOW_IPS to that address.
exec uv run gunicorn otzar.wsgi:application \
    --bind 0.0.0.0:8000 \
    --worker-class gthread \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" \
    --access-logfile - \
    --error-logfile -
