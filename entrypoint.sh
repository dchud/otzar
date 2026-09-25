#!/bin/sh
# Container entrypoint.
#
#   /entrypoint.sh          restore if needed, then serve under Litestream
#   /entrypoint.sh serve    migrate and run gunicorn (what Litestream runs)
#
# With a backup bucket configured, the database is replicated to
# s3://$AWS_S3_BACKUP_BUCKET/$LITESTREAM_REPLICA_PATH. LITESTREAM_MODE
# chooses how much of that happens: replicate (the default) restores a
# missing database and replicates; restore-only restores a missing
# database and serves without replicating, so a restore drill cannot
# write into production's replica; off, or an empty
# AWS_S3_BACKUP_BUCKET, does neither and serves directly.
#
# Before restoring, manage.py check_replica refuses a start that would
# serve or replicate the wrong data: a replica path a rebuild has moved
# on from, an empty start against a bucket that holds a replica, or a
# database behind its replica. The container then exits, and /health/
# stops answering.
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
    #
    # The access log's first field is X-Forwarded-For, which Caddy sets
    # to the client's address; the connection itself always comes from
    # the proxy. A request that bypasses Caddy logs "-".
    exec gunicorn otzar.wsgi:application \
        --bind 0.0.0.0:8000 \
        --worker-class gthread \
        --workers 2 \
        --threads 4 \
        --timeout 120 \
        --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" \
        --access-logfile - \
        --access-logformat '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"' \
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

mode=$(printf '%s' "${LITESTREAM_MODE:-replicate}" | tr '[:upper:]' '[:lower:]')
case "$mode" in
    replicate | restore-only | off) ;;
    *)
        echo "entrypoint: LITESTREAM_MODE is '$mode'; expected replicate, restore-only or off" >&2
        exit 1
        ;;
esac

if [ "$mode" = off ] || [ -z "${AWS_S3_BACKUP_BUCKET:-}" ]; then
    echo "entrypoint: Litestream is off (LITESTREAM_MODE=off or no AWS_S3_BACKUP_BUCKET); the database is neither restored nor replicated" >&2
    serve
fi

litestream-config > /etc/litestream.yml
python manage.py check_replica

# A fresh disk pulls the latest replicated copy before migrate runs. An
# existing database is left alone, and an empty replica (the first
# start) restores nothing and lets migrate create the database.
litestream restore -config /etc/litestream.yml \
    -if-db-not-exists -if-replica-exists \
    -o "$DATA_DIR/db.sqlite3" "$DATA_DIR/db.sqlite3"

if [ "$mode" = restore-only ]; then
    echo "entrypoint: LITESTREAM_MODE=restore-only; the database is not replicated" >&2
    serve
fi

# Replication runs while migrations write, and Litestream exits when
# gunicorn does. It forwards the container's stop signal to gunicorn and
# syncs the last changes before exiting.
exec litestream replicate -config /etc/litestream.yml \
    -exec "/entrypoint.sh serve"
