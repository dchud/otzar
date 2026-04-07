#!/usr/bin/env bash
set -e

HOOK_SRC="$(cd "$(dirname "$0")" && pwd)/pre-commit"
HOOK_DST="$(git rev-parse --show-toplevel)/.git/hooks/pre-commit"

if [ -e "$HOOK_DST" ] && [ ! -L "$HOOK_DST" ]; then
    echo "Error: $HOOK_DST already exists and is not a symlink."
    echo "Remove it manually if you want to replace it."
    exit 1
fi

ln -sf "$HOOK_SRC" "$HOOK_DST"
echo "Pre-commit hook installed."
