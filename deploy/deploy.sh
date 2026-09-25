#!/usr/bin/env bash
# Deploy one commit's image to the instance, with the same commit's
# deploy/ directory on standard input:
#
#   git archive <sha> deploy/ | ssh <host> sudo /opt/otzar/deploy.sh <sha>
#
# In order:
#
#   1. Unpacks the directory into releases/<sha>/. When that commit's
#      deploy.sh differs from the one running, runs it instead, so each
#      commit is deployed by its own steps.
#   2. If the app is running, takes a snapshot with snapshot_db. With no
#      image deployed before, or the app stopped, there is nothing to
#      snapshot, and it says so. Nothing on the host has changed yet.
#   3. Installs each file that differs from the one in place, so
#      compose.yml, the Caddyfile and these scripts always come from the
#      commit being deployed, and writes caddy.env, Caddy's
#      SITE_ADDRESS, from the first name in ALLOWED_HOSTS. When either
#      changed, Caddy is reloaded, or started if it is not running; if
#      Caddy refuses the result, the previous files are put back and the
#      deploy stops with the old image still running.
#   4. Pulls the image unless it is already on the host.
#   5. Sets OTZAR_IMAGE in .env to the image and starts it, so every
#      later docker compose command, and a reboot, uses the image
#      deployed last. If docker compose fails, OTZAR_IMAGE goes back to
#      the previous image. The entrypoint migrates the database before
#      gunicorn starts.
#   6. Waits up to 60 s for /health/ to answer through Caddy, prints the
#      moment to roll back to, and prints the age of the newest backups.
#
# Every failure up to the health check exits non-zero. The backup report
# at the end only warns, since the deploy has succeeded by then.
#
# Rolling back is `just rebuild --at <the printed moment>`, then `just
# deploy <the previous commit>`. The pre-deploy snapshot is the same
# state, but a later snapshot the same UTC day replaces it.
#
# Assumptions about the host, overridable from the environment:
#
#   OTZAR_HOME     /opt/otzar. Holds compose.yml and .env; `docker
#                  compose` run there manages the application.
#   APP_SERVICE    app. The compose service running the image.
#   IMAGE_REPO     ghcr.io/dchud/otzar. The image deployed is
#                  IMAGE_REPO:<sha>.
#   CADDY_RELOAD   systemctl reload-or-restart caddy. The command that
#                  makes Caddy re-read its configuration, starting it if
#                  it is not running.
set -euo pipefail

OTZAR_HOME=${OTZAR_HOME:-/opt/otzar}
APP_SERVICE=${APP_SERVICE:-app}
IMAGE_REPO=${IMAGE_REPO:-ghcr.io/dchud/otzar}
CADDY_RELOAD=${CADDY_RELOAD:-systemctl reload-or-restart caddy}

# shellcheck source=SCRIPTDIR/env-file.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env-file.sh"

die() {
    echo "deploy: $*" >&2
    exit 1
}

sha=${1:-}
# It reaches a root shell and names a directory; nothing else is valid.
[[ $# -eq 1 && $sha =~ ^[0-9a-f]{40}$ ]] ||
    die "usage: deploy.sh <40-character commit SHA>, with the deploy/ tree on standard input"

cd "$OTZAR_HOME"
[[ -f .env ]] || die "no .env in $OTZAR_HOME"

# The site's hostname: the first name in ALLOWED_HOSTS. Caddy serves it
# and the health check asks for it.
site=$(env_value ALLOWED_HOSTS)
site=${site%%,*}
[[ -n $site ]] || die "no ALLOWED_HOSTS in .env to name the site"

# 1. Unpack the deploy/ tree.
release=releases/$sha
if [[ -n ${DEPLOY_UNPACKED:-} ]]; then
    # Run by the previous deploy.sh, which has unpacked this tree.
    [[ -f $release/deploy.sh ]] || die "$release holds no deploy/ tree"
else
    [[ ! -t 0 ]] || die "expects the deploy/ tree on standard input, from git archive"
    rm -rf "$release"
    mkdir -p "$release"
    tar -x -f - -C "$release" --strip-components=1
    [[ -f $release/deploy.sh ]] || die "standard input held no deploy/ tree"
    if ! cmp -s "$release/deploy.sh" "${BASH_SOURCE[0]}"; then
        echo "deploy: running the deploy.sh from $sha"
        DEPLOY_UNPACKED=1 exec bash "$release/deploy.sh" "$sha"
    fi
fi

# What the host writes for itself. A file of the same name in the tree
# would replace it.
for name in .env caddy.env maintenance.caddy data releases; do
    [[ ! -e $release/$name ]] ||
        die "the deploy/ tree holds $name, which is the host's own; nothing was changed"
done

# 2. The pre-deploy snapshot, before anything on the host changes.
previous=$(env_value OTZAR_IMAGE)
if [[ -z $previous ]]; then
    echo "deploy: no image deployed before; no snapshot to take"
else
    # Assigned on its own line, so that a failing docker compose stops
    # the deploy rather than reading as "not running".
    running=$(docker compose ps --status running --quiet "$APP_SERVICE")
    if [[ -z $running ]]; then
        echo "deploy: $APP_SERVICE is not running; no snapshot to take"
    else
        docker compose exec -T "$APP_SERVICE" python manage.py snapshot_db
    fi
fi

# 3. Install the tree.
caddy_changed=0
while IFS= read -r -d '' file; do
    name=${file#"$release"/}
    if ! cmp -s "$file" "$name"; then
        if [[ $name == Caddyfile ]]; then
            caddy_changed=1
            [[ ! -f Caddyfile ]] || cp -p Caddyfile Caddyfile.previous
        fi
        mkdir -p "$(dirname "$name")"
        # Copied then renamed: bash reads a running script as it goes,
        # and this may be replacing deploy.sh itself.
        cp -p "$file" "$name.new"
        mv -f "$name.new" "$name"
        echo "deploy: installed $name"
    fi
    # git archive writes group-writable modes.
    chmod go-w "$name"
done < <(find "$release" -type f -print0)

# The Caddyfile imports this file; Caddy refuses a missing one.
[[ -f maintenance.caddy ]] || : > maintenance.caddy

if [[ $(cat caddy.env 2> /dev/null) != "SITE_ADDRESS=$site" ]]; then
    [[ ! -f caddy.env ]] || cp -p caddy.env caddy.env.previous
    echo "SITE_ADDRESS=$site" > caddy.env
    chmod 0644 caddy.env
    caddy_changed=1
    echo "deploy: wrote caddy.env: SITE_ADDRESS=$site"
fi

if [[ $caddy_changed -eq 1 ]]; then
    if eval "$CADDY_RELOAD"; then
        rm -f Caddyfile.previous caddy.env.previous
        echo "deploy: Caddy reloaded"
    else
        [[ ! -f Caddyfile.previous ]] || mv -f Caddyfile.previous Caddyfile
        [[ ! -f caddy.env.previous ]] || mv -f caddy.env.previous caddy.env
        die "Caddy refused the new configuration; the previous Caddyfile and caddy.env are back in place and ${previous:-no image} is still running"
    fi
fi

# 4. The image.
image=$IMAGE_REPO:$sha
if ! docker image inspect "$image" > /dev/null 2>&1; then
    docker pull "$image" ||
        die "cannot pull $image; ${previous:-no image} is still running"
fi

# 5. Start it. The moment before the switch is the state to roll back
# to.
rollback_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
set_env_value OTZAR_IMAGE "$image"
echo "deploy: starting $image (previously ${previous:-none})"
if ! docker compose up -d; then
    set_env_value OTZAR_IMAGE "$previous"
    die "docker compose up failed; OTZAR_IMAGE is back to ${previous:-empty}"
fi

# 6. Check it: straight to Caddy on this host, whatever DNS and the
# firewall say, with the site's name for the certificate and the Host
# header.
deadline=$((SECONDS + 60))
until curl -fs -o /dev/null --max-time 5 \
    --resolve "$site:443:127.0.0.1" "https://$site/health/"; do
    ((SECONDS < deadline)) ||
        die "https://$site/health/ did not answer within 60 s; check: docker compose logs $APP_SERVICE"
    sleep 2
done
echo "deploy: https://$site/health/ answers"

if [[ -n $previous ]]; then
    echo "deploy: to roll back: just rebuild --at $rollback_at, then just deploy ${previous##*:}"
fi
docker compose exec -T "$APP_SERVICE" python manage.py backup_status ||
    echo "deploy: backup_status failed; the deploy itself succeeded" >&2
echo "deploy: done, $image"
