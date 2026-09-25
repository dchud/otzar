#!/usr/bin/env bash
# Write the application's .env from the deployment's template.
#
#   scripts/configure.sh --local DIR
#
# --local writes DIR/.env for the local rehearsal (scripts/rehearsal/):
# the site at otzar.localhost, moto at s3.otzar.localhost standing in
# for both buckets, a generated site password and no Anthropic key, so
# OCR is not available there. An existing DIR/.env is left alone.
#
# The template's values come from four places:
#
#   generated       SECRET_KEY
#   fixed here      DEBUG, DATA_DIR, TIME_ZONE, CLAUDE_MODEL,
#                   OCR_DAILY_CALL_CAP, RECORD_ID_PREFIX,
#                   FORWARDED_ALLOW_IPS, LITESTREAM_REPLICA_PATH
#   the hostname    ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
#   supplied        the buckets, region, endpoint and access key; the
#                   secrets SITE_PASSWORD, ANTHROPIC_API_KEY and
#                   BACKUP_PING_URL
set -euo pipefail

usage() {
    echo "usage: scripts/configure.sh --local DIR" >&2
    exit 2
}

[[ $# -eq 2 && $1 == --local ]] || usage
dir=$2

site=otzar.localhost
secret_key=$(openssl rand -hex 32)
site_password=$(openssl rand -hex 8)
anthropic_api_key=
backup_ping_url=
media_bucket=otzar-media
backup_bucket=otzar-backup
region=us-east-1
endpoint_url=http://s3.otzar.localhost:9000
access_key_id=rehearsal
secret_access_key=rehearsal

template() {
    cat <<EOF
# Written by scripts/configure.sh. Holds secrets: mode 0600.
SECRET_KEY=$secret_key
DEBUG=false
ALLOWED_HOSTS=$site
CSRF_TRUSTED_ORIGINS=https://$site
# Inside the container; compose.yml mounts ./data here.
DATA_DIR=/data
TIME_ZONE=America/New_York
CLAUDE_MODEL=claude-sonnet-5
OCR_DAILY_CALL_CAP=500
RECORD_ID_PREFIX=otzar-
# The gateway of the fixed subnet in compose.yml, which is where Caddy's
# requests arrive from.
FORWARDED_ALLOW_IPS=172.30.0.1
SITE_PASSWORD=$site_password
ANTHROPIC_API_KEY=$anthropic_api_key
BACKUP_PING_URL=$backup_ping_url
AWS_S3_MEDIA_BUCKET=$media_bucket
AWS_S3_BACKUP_BUCKET=$backup_bucket
AWS_S3_REGION=$region
AWS_ACCESS_KEY_ID=$access_key_id
AWS_SECRET_ACCESS_KEY=$secret_access_key
LITESTREAM_REPLICA_PATH=litestream/db
EOF
    if [[ -n $endpoint_url ]]; then
        echo "AWS_S3_ENDPOINT_URL=$endpoint_url"
    fi
}

if [[ -e $dir/.env ]]; then
    echo "configure: $dir/.env exists; leaving it alone" >&2
    exit 0
fi
mkdir -p "$dir"
(
    umask 077
    template > "$dir/.env"
)
echo "configure: wrote $dir/.env"
echo "configure: site password: $site_password"
