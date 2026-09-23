#!/bin/sh
# Container entrypoint.
#
#   /entrypoint.sh          restore if needed, then serve under Litestream
#   /entrypoint.sh serve    migrate and run gunicorn (what Litestream runs)
#
# With a backup bucket configured, the database is replicated to
# s3://$AWS_S3_BACKUP_BUCKET/$LITESTREAM_REPLICA_PATH. LITESTREAM_DISABLED=1,
# or an empty AWS_S3_BACKUP_BUCKET, skips both the restore and the
# replication and serves directly: an instance started from a copy of
# production for a restore drill must not write into production's replica.
set -eu

serve() {
    python manage.py migrate --noinput

    # Threads rather than sync workers: OCR and the SRU cascade both run
    # inside the request and can each hold it for tens of seconds, and
    # with two sync workers two such requests would stall every other
    # page.
    #
    # --forwarded-allow-ips names the proxy whose X-Forwarded-* headers
    # gunicorn passes through to Django. gunicorn's default, 127.0.0.1,
    # is the proxy only when both share a network namespace; with the
    # proxy on the host and gunicorn in a container, requests arrive
    # from the Docker bridge, so the deployment sets FORWARDED_ALLOW_IPS
    # to that address.
    exec gunicorn otzar.wsgi:application \
        --bind 0.0.0.0:8000 \
        --worker-class gthread \
        --workers 2 \
        --threads 4 \
        --timeout 120 \
        --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" \
        --access-logfile - \
        --error-logfile -
}

if [ "${1:-}" = serve ]; then
    serve
fi

# Without DATA_DIR the settings fall back to the project directory, and
# /app is the image's own filesystem: the catalog would be written into
# the container and discarded by the next deploy. Anything under /app is
# refused for the same reason.
if [ -z "${DATA_DIR:-}" ]; then
    echo "entrypoint: DATA_DIR is not set; point it at the mounted data directory" >&2
    exit 1
fi
DATA_DIR=$(realpath -m "$DATA_DIR")
export DATA_DIR
case "$DATA_DIR" in
    /app | /app/*)
        echo "entrypoint: DATA_DIR is $DATA_DIR, inside the image; point it at the mounted data directory" >&2
        exit 1
        ;;
esac
mkdir -p "$DATA_DIR"

case "$(printf '%s' "${LITESTREAM_DISABLED:-}" | tr '[:upper:]' '[:lower:]')" in
    1 | true | yes) litestream_disabled=1 ;;
    *) litestream_disabled= ;;
esac

if [ -n "$litestream_disabled" ] || [ -z "${AWS_S3_BACKUP_BUCKET:-}" ]; then
    echo "entrypoint: Litestream is off (LITESTREAM_DISABLED set or no AWS_S3_BACKUP_BUCKET); the database is not replicated" >&2
    serve
fi

litestream-config > /etc/litestream.yml

# A fresh disk pulls the latest replicated copy before migrate runs. An
# existing database is left alone, and an empty replica (the first
# start) restores nothing and lets migrate create the database.
litestream restore -config /etc/litestream.yml \
    -if-db-not-exists -if-replica-exists \
    -o "$DATA_DIR/db.sqlite3" "$DATA_DIR/db.sqlite3"

# Replication runs while migrations write, and Litestream exits when
# gunicorn does. It forwards the container's stop signal to gunicorn and
# syncs the last changes before exiting.
exec litestream replicate -config /etc/litestream.yml \
    -exec "/entrypoint.sh serve"
