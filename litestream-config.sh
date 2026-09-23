#!/bin/sh
# Print a Litestream configuration for the database, built from the
# environment.
#
#   litestream-config [REPLICA_PATH] > /etc/litestream.yml
#
# REPLICA_PATH defaults to LITESTREAM_REPLICA_PATH, then litestream/db.
# rebuild.sh passes another path to restore from a replica that is no
# longer the current one.
#
# Reads DATA_DIR, AWS_S3_BACKUP_BUCKET, AWS_S3_REGION and, for an
# S3-compatible service other than AWS, AWS_S3_ENDPOINT_URL.
# Credentials are not written here: Litestream reads AWS_ACCESS_KEY_ID
# and AWS_SECRET_ACCESS_KEY from the environment itself.
set -eu

replica_path=${1:-${LITESTREAM_REPLICA_PATH:-litestream/db}}
# Leading and trailing slashes would give an empty path segment.
replica_path=$(printf '%s' "$replica_path" | sed 's#^/*##; s#/*$##')

: "${DATA_DIR:?DATA_DIR is not set}"
: "${AWS_S3_BACKUP_BUCKET:?AWS_S3_BACKUP_BUCKET is not set}"

# Values are written as double-quoted YAML strings. None of them can
# contain a double quote or a backslash in a valid configuration, and
# refusing one here is clearer than a YAML error from Litestream.
for value in "$DATA_DIR" "$AWS_S3_BACKUP_BUCKET" "$replica_path" \
    "${AWS_S3_REGION:-}" "${AWS_S3_ENDPOINT_URL:-}"; do
    case "$value" in
        *\"* | *\\*)
            echo "litestream-config: refusing a value with a quote or backslash: $value" >&2
            exit 1
            ;;
    esac
done

cat <<EOF
# Written by litestream-config from the environment; edits are lost.
dbs:
  - path: "${DATA_DIR%/}/db.sqlite3"
    replica:
      type: s3
      bucket: "$AWS_S3_BACKUP_BUCKET"
      path: "$replica_path"
      region: "${AWS_S3_REGION:-us-east-1}"
EOF

# A stand-in such as moto or SeaweedFS answers on one host name, so
# the bucket goes in the path rather than in the host name.
if [ -n "${AWS_S3_ENDPOINT_URL:-}" ]; then
    cat <<EOF
      endpoint: "$AWS_S3_ENDPOINT_URL"
      force-path-style: true
EOF
fi

# A full snapshot a day, and seven days of them: any moment in the last
# week can be restored with -timestamp. Litestream's default retention
# is a day, too short for a mistake noticed the next morning.
cat <<EOF
snapshot:
  interval: 24h
  retention: 168h
EOF
