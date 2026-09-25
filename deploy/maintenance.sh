#!/usr/bin/env bash
# Show or clear the maintenance page, on the instance.
#
#   maintenance.sh on|off
#
# On copies maintenance-on.caddy over maintenance.caddy, which the site
# block imports: every request except /health/ gets a 503 page. Off
# empties maintenance.caddy. Caddy is reloaded either way, which drops
# no connections. The app, Litestream and the timers keep running, so
# nothing is lost while the page is up.
#
# Assumptions about the host, overridable from the environment:
#
#   OTZAR_HOME     /opt/otzar. Holds the Caddyfile and maintenance.caddy.
#   CADDY_RELOAD   systemctl reload-or-restart caddy. The command that
#                  makes Caddy re-read its configuration, starting it if
#                  it is not running.
set -euo pipefail

OTZAR_HOME=${OTZAR_HOME:-/opt/otzar}
CADDY_RELOAD=${CADDY_RELOAD:-systemctl reload-or-restart caddy}

cd "$OTZAR_HOME"
live=$OTZAR_HOME/maintenance.caddy

case "${1:-}" in
    on) source=$OTZAR_HOME/maintenance-on.caddy ;;
    off) source=/dev/null ;;
    *)
        echo "usage: maintenance.sh on|off" >&2
        exit 2
        ;;
esac

# Kept so a configuration Caddy refuses leaves the file matching what
# Caddy is still serving.
previous=$(mktemp)
trap 'rm -f "$previous"' EXIT
if [[ -f $live ]]; then
    cp "$live" "$previous"
fi

cat "$source" > "$live.new"
chmod 0644 "$live.new"
mv -f "$live.new" "$live"

if ! eval "$CADDY_RELOAD"; then
    cp "$previous" "$live"
    echo "maintenance: Caddy refused the new configuration; maintenance.caddy is restored" >&2
    exit 1
fi
echo "maintenance: $1"
