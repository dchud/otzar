#!/usr/bin/env bash
# Rehearse the deployment on this machine: the real image, the real
# deploy/ files and host scripts, Caddy at https://otzar.localhost and
# moto standing in for S3. Everything but Lightsail, its firewall and
# DNS runs as it will on the instance.
#
#   rehearse.sh up [COMMIT]         set up the rehearsal if needed, then
#                                   deploy COMMIT (default HEAD)
#   rehearse.sh deploy COMMIT       deploy another commit, as `just
#                                   deploy` does on the instance
#   rehearse.sh rebuild ARGS...     rebuild.sh, as `just rebuild` runs it
#   rehearse.sh maintenance on|off  maintenance.sh
#   rehearse.sh manage ARGS...      a management command in the app
#   rehearse.sh compose ARGS...     docker compose in the rehearsal
#   rehearse.sh down                remove the containers; moto's buckets
#                                   go with them
#   rehearse.sh clean               down, then delete the rehearsal
#                                   directory
#
# tmp/rehearsal/home stands in for /opt/otzar. The first `up` fills it
# as provisioning fills /opt/otzar: the commit's deploy/ files, an empty
# maintenance.caddy, and a .env from `scripts/configure.sh --local`,
# plus COMPOSE_FILE naming scripts/rehearsal/compose.yml beside
# compose.yml. Every later step runs the installed host scripts there,
# with their host assumptions overridden for this machine.
#
# The host scripts run as root where the Docker daemon runs, as they do
# on the instance. Under Colima that is its Ubuntu VM, reached with
# `colima ssh`, which sees this directory at the same path. It also sees
# files as the containers do: macOS's view of a bind mount lags a rename
# by a second or two, and rebuild.sh moves the database aside and then
# restores into its place. Without Colima they run in this shell.
#
# Every docker compose command for the rehearsal runs there too. Compose
# versions differ in how they fingerprint a service, so a second Compose
# on the Mac would recreate containers the first one left running,
# moto's in-memory buckets among them.
#
# Images are built from the commit, not the working tree: the commit is
# unpacked with git archive and built from there, tagged otzar:<sha>, so
# an uncommitted change never reaches the rehearsal, as it never reaches
# production.
#
# https://otzar.localhost is signed by Caddy's local authority. Its root
# certificate is tmp/rehearsal/home/caddy/caddy/pki/authorities/local/
# root.crt; the scripts here trust it, and a browser warns until it is
# trusted or the warning is accepted.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
home=$repo/tmp/rehearsal/home
root_cert=$home/caddy/caddy/pki/authorities/local/root.crt

# The host scripts' assumptions, for this machine.
host_env=(
    OTZAR_HOME="$home"
    IMAGE_REPO=otzar
    CADDY_RELOAD="docker compose exec -T caddy caddy reload --config /opt/otzar/Caddyfile --adapter caddyfile"
    CURL_CA_BUNDLE="$root_cert"
)

die() {
    echo "rehearse: $*" >&2
    exit 1
}

# Run a host script, as root where the Docker daemon runs.
on_host() {
    local context
    context=$(docker context show 2>/dev/null || true)
    case $context in
        colima) colima ssh -- sudo env "${host_env[@]}" "$@" ;;
        colima-*)
            colima ssh --profile "${context#colima-}" -- \
                sudo env "${host_env[@]}" "$@"
            ;;
        *) env "${host_env[@]}" "$@" ;;
    esac
}

usage() {
    sed -n '7,18p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
}

commit() {
    git -C "$repo" rev-parse --verify --quiet "$1^{commit}" ||
        die "not a commit: $1"
}

build() {
    local sha=$1
    if docker image inspect "otzar:$sha" > /dev/null 2>&1; then
        return
    fi
    echo "rehearse: building otzar:$sha"
    # Unpacked into a directory rather than piped in as a tar: docker
    # applies .dockerignore only when it packs a directory itself, and
    # CI builds from a checkout.
    local context=$repo/tmp/rehearsal/build
    rm -rf "$context"
    mkdir -p "$context"
    git -C "$repo" archive "$sha" | tar -x -f - -C "$context"
    docker build --build-arg GIT_COMMIT="$sha" -t "otzar:$sha" "$context"
    rm -rf "$context"
}

provision() {
    local sha=$1
    echo "rehearse: setting up $home"
    mkdir -p "$home"
    git -C "$repo" archive "$sha" deploy/ |
        tar -x -f - -C "$home" --strip-components=1
    : > "$home/maintenance.caddy"
    "$repo/scripts/configure.sh" --local "$home"
    echo "COMPOSE_FILE=compose.yml:$repo/scripts/rehearsal/compose.yml" \
        >> "$home/.env"
}

deploy() {
    local sha
    sha=$(commit "$1")
    build "$sha"
    [[ -f $home/.env ]] || provision "$sha"
    git -C "$repo" archive "$sha" deploy/ | on_host "$home/deploy.sh" "$sha"
}

in_home() {
    [[ -f $home/.env ]] || die "no rehearsal in $home; run: just rehearse up"
    cd "$home"
}

[[ $# -ge 1 ]] || usage
action=$1
shift
case $action in
    up)
        [[ $# -le 1 ]] || usage
        deploy "${1:-HEAD}"
        ;;
    deploy)
        [[ $# -eq 1 ]] || usage
        [[ -f $home/.env ]] || die "no rehearsal in $home; run: just rehearse up"
        deploy "$1"
        ;;
    rebuild)
        in_home
        on_host "$home/rebuild.sh" "$@"
        ;;
    maintenance)
        in_home
        on_host "$home/maintenance.sh" "$@"
        ;;
    manage)
        in_home
        on_host docker compose exec app python manage.py "$@"
        ;;
    compose)
        in_home
        on_host docker compose "$@"
        ;;
    down)
        in_home
        on_host docker compose down
        ;;
    clean)
        if [[ -f $home/.env ]]; then
            in_home
            on_host docker compose down
        fi
        rm -rf "$home"
        echo "rehearse: removed $home"
        ;;
    *) usage ;;
esac
