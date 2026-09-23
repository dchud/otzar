#!/usr/bin/env bash
# Rebuild the catalog database from a backup, on the instance.
#
#   rebuild.sh --latest [--from REPLICA_PATH]
#   rebuild.sh --at TIME [--from REPLICA_PATH]
#   rebuild.sh --snapshot YYYY-MM-DD|YYYY-MM
#
#   --latest     the replica's current state
#   --at TIME    the replica's state at TIME (RFC 3339, e.g.
#                2026-09-22T14:00:00Z), within its seven days of history
#   --snapshot   a daily snapshot (YYYY-MM-DD, kept 35 days) or the
#                monthly one taken on the 1st (YYYY-MM, kept 13 months)
#   --from PATH  restore from this replica path instead of the one in
#                .env, such as the path in use before an earlier rebuild
#
# Stops the app, moves the database aside under
# $HOST_DATA_DIR/pre-rebuild/<timestamp>/, restores, points
# LITESTREAM_REPLICA_PATH in .env at a new, empty replica path, starts
# the app and reports what it restored. Replication resumes into the
# new path, so the history in the old one -- which may be needed if the
# chosen point proves wrong -- is never written over. The old path is
# left for the bucket's lifecycle rules to expire.
#
# Assumptions about the host, overridable from the environment:
#
#   OTZAR_HOME     /opt/otzar. Holds compose.yml and .env; `docker
#                  compose` run there manages the application.
#   APP_SERVICE    app. The compose service running the image, which
#                  carries litestream, litestream-config and manage.py.
#   HOST_DATA_DIR  $OTZAR_HOME/data. The host directory mounted into
#                  that service as its DATA_DIR.
#
# .env sets DATA_DIR (the path inside the container) and
# AWS_S3_BACKUP_BUCKET, and may set LITESTREAM_REPLICA_PATH.
set -euo pipefail

OTZAR_HOME=${OTZAR_HOME:-/opt/otzar}
APP_SERVICE=${APP_SERVICE:-app}
HOST_DATA_DIR=${HOST_DATA_DIR:-$OTZAR_HOME/data}
DEFAULT_REPLICA_PATH=litestream/db

usage() {
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
}

die() {
    echo "rebuild: $*" >&2
    exit 1
}

mode=
point=
from=
while [[ $# -gt 0 ]]; do
    case "$1" in
        --latest)
            [[ -z $mode ]] || usage
            mode=latest
            shift
            ;;
        --at | --snapshot)
            [[ -z $mode && $# -ge 2 ]] || usage
            mode=${1#--}
            point=$2
            shift 2
            ;;
        --from)
            [[ -z $from && $# -ge 2 ]] || usage
            from=$2
            shift 2
            ;;
        *) usage ;;
    esac
done
[[ -n $mode ]] || usage
if [[ -n $from && $mode == snapshot ]]; then
    die "--from applies to --latest and --at, not --snapshot"
fi
# These reach a shell inside the container; allow only what they need.
if [[ -n $from && ! $from =~ ^[A-Za-z0-9._/-]+$ ]]; then
    die "--from: not a replica path: $from"
fi
if [[ $mode == at && ! $point =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+(Z|[+-][0-9]{2}:[0-9]{2})$ ]]; then
    die "--at: not an RFC 3339 time: $point"
fi
if [[ $mode == snapshot && ! $point =~ ^[0-9]{4}-[0-9]{2}(-[0-9]{2})?$ ]]; then
    die "--snapshot: not YYYY-MM-DD or YYYY-MM: $point"
fi

cd "$OTZAR_HOME"
[[ -f compose.yml ]] || die "no compose.yml in $OTZAR_HOME"
[[ -f .env ]] || die "no .env in $OTZAR_HOME"

# The last assignment of KEY in .env, without surrounding quotes.
env_value() {
    sed -n "s/^$1=//p" .env | tail -n 1 | sed "s/^[\"']//; s/[\"']\$//"
}

# Replace KEY's line in .env, or append one. The file is rewritten
# with mode 0600, since it holds the instance's secrets.
set_env_value() {
    local key=$1 value=$2
    (
        umask 077
        awk -v key="$key" -v value="$value" '
            index($0, key "=") == 1 {
                if (!done) print key "=" value
                done = 1
                next
            }
            { print }
            END { if (!done) print key "=" value }
        ' .env > .env.rebuild
    )
    mv .env.rebuild .env
}

current=$(env_value LITESTREAM_REPLICA_PATH)
current=${current:-$DEFAULT_REPLICA_PATH}
source_path=${from:-$current}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
new_path=litestream/db-$stamp
aside=$HOST_DATA_DIR/pre-rebuild/$stamp

case $mode in
    latest) echo "rebuild: restoring the latest state of $source_path" ;;
    at) echo "rebuild: restoring $source_path as of $point" ;;
    snapshot) echo "rebuild: restoring the snapshot for $point" ;;
esac

docker compose stop "$APP_SERVICE"

# Everything SQLite and Litestream keep beside the database. The
# Litestream directory holds its position in the old database; left in
# place, it would describe a database that is no longer there.
mkdir -p "$aside"
moved=0
for name in db.sqlite3 db.sqlite3-wal db.sqlite3-shm .db.sqlite3-litestream; do
    if [[ -e $HOST_DATA_DIR/$name ]]; then
        mv "$HOST_DATA_DIR/$name" "$aside/"
        moved=1
    fi
done
if [[ $moved -eq 1 ]]; then
    echo "rebuild: previous database moved to $aside"
else
    rmdir "$aside"
    echo "rebuild: there was no database in $HOST_DATA_DIR"
fi

# shellcheck disable=SC2329  # invoked by the ERR trap
failed() {
    echo "rebuild: failed; the app is left stopped and .env is unchanged." >&2
    if [[ $moved -eq 1 ]]; then
        echo "rebuild: the previous database is in $aside. To go back to it," \
            "remove any db.sqlite3 in $HOST_DATA_DIR, move everything in" \
            "$aside (including .db.sqlite3-litestream) back, and run" \
            "docker compose start $APP_SERVICE in $OTZAR_HOME." >&2
    fi
}
trap failed ERR

# One-off containers of the app image, with its .env and data mount but
# not its entrypoint, so nothing starts replicating yet.
case $mode in
    latest | at)
        # $1 is the replica path; $2 the time, empty for --latest.
        # shellcheck disable=SC2016  # expanded by the container's shell
        docker compose run --rm --no-deps -T --entrypoint sh "$APP_SERVICE" -c '
            set -eu
            db="${DATA_DIR%/}/db.sqlite3"
            litestream-config "$1" > /etc/litestream-rebuild.yml
            if [ -n "$2" ]; then set -- -timestamp "$2"; else set --; fi
            litestream restore -config /etc/litestream-rebuild.yml \
                -o "$db" "$@" "$db"
        ' sh "$source_path" "$point"
        ;;
    snapshot)
        docker compose run --rm --no-deps -T --entrypoint python "$APP_SERVICE" \
            manage.py fetch_snapshot "$point"
        ;;
esac

[[ -f $HOST_DATA_DIR/db.sqlite3 ]] ||
    { echo "rebuild: no database at $HOST_DATA_DIR/db.sqlite3 after the restore" >&2; false; }

set_env_value LITESTREAM_REPLICA_PATH "$new_path"
trap - ERR
echo "rebuild: LITESTREAM_REPLICA_PATH is now $new_path in $OTZAR_HOME/.env"

# Recreated rather than restarted: a restart does not re-read .env.
# --no-deps keeps --force-recreate from recreating anything else.
docker compose up -d --force-recreate --no-deps "$APP_SERVICE"

report='
from catalog.models import Record
newest = Record.objects.order_by("-created_at").first()
print("records:", Record.objects.count())
print("newest record created:", newest.created_at.isoformat() if newest else "none")
'
for _ in $(seq 1 30); do
    if summary=$(docker compose exec -T "$APP_SERVICE" python manage.py shell -v 0 -c "$report" 2>/dev/null); then
        break
    fi
    summary=
    sleep 2
done

echo
echo "rebuild: done"
if [[ -n $summary ]]; then
    echo "$summary"
else
    echo "the app did not answer within 60 s; check: docker compose logs $APP_SERVICE"
fi
echo "replica path in use: $new_path"
echo "previous replica path, left in place: $current"
[[ $moved -eq 1 ]] && echo "previous database: $aside"
exit 0
