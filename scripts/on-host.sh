#!/usr/bin/env bash
# Run one of the host scripts in /opt/otzar on the instance, as root
# over SSH, with the arguments given:
#
#   scripts/on-host.sh rebuild.sh --latest
#
# DEPLOY_HOST is the SSH destination, from the environment or the local
# .env.
set -euo pipefail

host=${DEPLOY_HOST:-$(sed -n 's/^DEPLOY_HOST=//p' .env 2>/dev/null | tail -n 1)}
if [[ -z $host ]]; then
    echo "on-host: set DEPLOY_HOST in .env or the environment" >&2
    exit 1
fi
[[ $# -ge 1 ]] || {
    echo "usage: scripts/on-host.sh SCRIPT [ARGS...]" >&2
    exit 2
}
command="sudo /opt/otzar/$1"
shift
# ssh joins its arguments into one line for the remote shell; quoting
# each keeps an argument with a space in it one argument. (printf with
# no arguments would still print the format once, adding an empty one.)
if [[ $# -gt 0 ]]; then
    command+=$(printf ' %q' "$@")
fi
exec ssh "$host" "$command"
