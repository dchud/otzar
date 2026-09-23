# Administration guide

System administration reference for the otzar catalog application.

## Configuration reference

All configuration is via environment variables, loaded from a `.env` file or
set in the environment of the running process. See `.env.example` for a
template.

### Django core

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes (production) | Insecure dev fallback | Django secret key. With `DEBUG` false the app refuses to start on the fallback or an empty value. Generate with: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | No | `true` | Set to `false` in production. Accepts `true`, `1`, `yes` (case-insensitive). |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated list of hostnames the app will serve. In production, set to the hostname the site is served from. |
| `CSRF_TRUSTED_ORIGINS` | No | (empty) | Comma-separated list of origins for CSRF validation. Set to the full site URL including scheme (e.g. `https://catalog.example.org`). |
| `DATA_DIR` | No | Project root | Directory for the SQLite database, cache, and media files. In production, point it at storage that survives a restart or a rebuilt container. Locally, defaults to the project directory. |
| `FORWARDED_ALLOW_IPS` | Yes (production) | `127.0.0.1` | Address of the reverse proxy, read by `entrypoint.sh` and passed to gunicorn's `--forwarded-allow-ips`. Gunicorn passes `X-Forwarded-*` headers through to Django only from this address. With the proxy on the host and the app in a container, set it to the Docker bridge address the proxy's requests arrive from. |

### Title page OCR through the Anthropic API

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | For title page scanning | (none) | Anthropic API key. Required only if using title page photograph/OCR ingest. Not needed for ISBN scan or manual entry. |
| `CLAUDE_MODEL` | No | `claude-sonnet-5` | Model used for OCR. Sonnet reads Hebrew decorative type more accurately than Haiku. |

### Media storage on S3

Uploaded images are stored in `DATA_DIR/media` unless `AWS_S3_MEDIA_BUCKET` is
set, in which case they go to that bucket. The bucket is private: every image
link the app renders is a presigned URL, valid for six hours.

| Variable | Required | Default | Description |
|---|---|---|---|
| `AWS_S3_MEDIA_BUCKET` | No | (none) | S3 bucket for uploaded images. Unset keeps media on the local filesystem. |
| `AWS_S3_REGION` | No | `us-east-1` | Region of the bucket. |
| `AWS_ACCESS_KEY_ID` | With a bucket | (none) | Access key for the bucket, read by boto3. Can be omitted on a host with an instance role. |
| `AWS_SECRET_ACCESS_KEY` | With a bucket | (none) | Secret for that key. |
| `AWS_S3_ENDPOINT_URL` | No | (none) | Endpoint of another S3-compatible service, such as MinIO. Unset uses AWS. |

### SRU catalog endpoints

| Variable | Required | Default | Description |
|---|---|---|---|
| `SRU_NLI_URL` | No | `https://nli.alma.exlibrisgroup.com/view/sru/972NNL_INST` | National Library of Israel SRU endpoint. |
| `SRU_LC_URL` | No | `http://lx2.loc.gov:210/LCDB` | Library of Congress SRU endpoint. |
| `SRU_VIAF_URL` | No | `https://viaf.org/viaf/search` | VIAF authority search endpoint. |
| `SRU_REQUEST_DELAY` | No | `3` | Seconds to wait between requests to external catalogs. Respects rate limits on public endpoints. |

### Site settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `RECORD_ID_PREFIX` | No | `otzar-` | Prefix for generated record identifiers (e.g. `otzar-3f8a`). Change this if deploying for a different community. |
| `SITE_PASSWORD` | No | (empty) | If set, all public pages require this password before access. Authenticated users (catalogers) and the admin, login, and health check pages bypass this gate. Clear the variable to disable the gate. |


## Routine operations

### Creating user accounts

Cataloger accounts are standard Django user accounts. Create them in one of two
ways:

**Via Django admin** (preferred for ongoing use): Log in at `/admin/`, go to
Users, and add a new user. Staff status is not required for cataloging; any
authenticated user can access ingest features.

**Via command line** (initial setup):

```bash
uv run python manage.py createsuperuser
# or with just:
just createsuperuser
```

### Password resets and lockouts

A logged-in user changes their own password at `/accounts/password_change/`,
linked from their username in the header. The app sends no email, so there is
no self-service reset of a forgotten password. An administrator sets a new
password in the admin: open Users, choose the user, and use the password form
linked from the Password field.

Five failed logins for one username from one address lock that username out
from that address for an hour, on both the site login and the admin login.
Other usernames, and the same username from another address, are not affected.
A successful login clears the count. To clear a lockout before the hour is up:

```bash
uv run python manage.py axes_reset_username <username>
# or every lockout at once:
uv run python manage.py axes_reset
```

The lockout period is `AXES_COOLOFF_TIME` in `otzar/settings.py`; the lockout
page, `templates/registration/lockout.html`, states it too.

### Setting or clearing the site-wide password

The site-wide password is controlled entirely by the `SITE_PASSWORD`
environment variable.

- **Set it**: Add `SITE_PASSWORD=yourpassword` to `.env`, or set it in the
  environment the app runs in. The app reads this at startup.
- **Clear it**: Remove the variable or set it to an empty string. Restart the
  app for the change to take effect.

When active, unauthenticated visitors see a password prompt. Once entered
correctly, the password is stored in the session. Logged-in catalogers bypass
the gate entirely.

### Applying code updates

```bash
git pull
uv sync
uv run python manage.py migrate
```

Restart the app afterwards so it picks up the new code and any changed
environment variables.

The container image built from `Dockerfile` handles the migration step on its
own: `entrypoint.sh` runs `manage.py migrate --noinput` before starting
gunicorn, so restarting the container applies pending migrations.

Migrations are written to be non-destructive. Review each migration before
merging it.

### Loading test data

Populates the database with representative sample records for development or
demos:

```bash
uv run python manage.py load_test_data
# or:
just load-test-data
```

This creates sample authors, publishers, subjects, series, locations, and
catalog records. It uses `get_or_create` and is safe to run multiple times.


## Management commands

### `load_test_data`

Loads representative test data (authors, records, series, locations) for
development and demos.

```bash
uv run python manage.py load_test_data
```

No arguments. Uses `get_or_create`, so running it again does not duplicate
data.

### `reindex`

Rebuilds the full-text search index (`catalog_fts`) from the catalog records.

```bash
uv run python manage.py reindex
```

No arguments. It drops the index table, recreates it and fills it from
every record in one transaction, then reports how many records it
indexed. A record it cannot index is skipped and listed by record id
rather than aborting the rebuild.

The application rebuilds the index by itself when the set of indexed
fields changes, so this is for recovery: after restoring a database, or
when search returns nothing for queries that should match.

### `cleanup_staging`

Deletes old discarded scan results and orphaned staging images. It
reports what it would delete and removes nothing unless `--apply` is
passed, because none of these deletions can be undone.

```bash
uv run python manage.py cleanup_staging [--days N] [--apply]
```

| Option | Default | Description |
|---|---|---|
| `--days` | 30 | Retention period in days. Discarded `ScanResult` records and orphaned staging images older than this are removed. |
| `--apply` | off | Delete. Without it the command writes nothing. |

This removes:
1. `ScanResult` objects with status `discarded` where `updated_at` is older
   than the cutoff, and the image file each one holds.
2. Files under `MEDIA_ROOT/staging/` that no `ScanResult` references, whose
   filesystem modification time is older than the cutoff.

Scans awaiting OCR are left alone at any age. They are unfinished work
rather than rejected work, and nothing else in the application removes
them.

Run periodically (e.g. weekly via cron or an equivalent scheduler) to reclaim
storage.


## Backup and restore

What is worth keeping:

- `DATA_DIR/db.sqlite3` -- the catalog database, including the full-text
  search index.
- Uploaded images -- in `DATA_DIR/media/`, or in the media bucket when
  `AWS_S3_MEDIA_BUCKET` is set.
- `DATA_DIR/cache/` -- the file-based cache. Derived from the database; no
  need to back it up.

### Backing up the database

SQLite runs in WAL mode, so copying `db.sqlite3` while the app is writing can
capture an inconsistent file. Use the SQLite backup command, which is safe
against a live database:

```bash
sqlite3 "$DATA_DIR/db.sqlite3" ".backup /path/to/backup.sqlite3"
```

The alternative is to stop the app first and copy `db.sqlite3` along with any
`db.sqlite3-wal` and `db.sqlite3-shm` files beside it.

On the filesystem, media files are ordinary files. Copy `media/` with `rsync`
or an equivalent tool.

In the media bucket, the backup is the bucket's versioning: an overwritten or
deleted image stays as a noncurrent version for 30 days. Recovering one means
restoring that version with an administrator's AWS identity, since the key the
app runs with cannot read old versions:

```bash
aws s3api list-object-versions --bucket <bucket> --prefix <image key>
aws s3api copy-object --bucket <bucket> --key <image key> \
    --copy-source "<bucket>/<image key>?versionId=<version id>"
```

Restoring the database does not require restoring the bucket: the records
point at object keys, and the objects stay where they are.

### Restoring

1. Stop the app.
2. Put the database file back at `DATA_DIR/db.sqlite3`, deleting any stale
   `db.sqlite3-wal` and `db.sqlite3-shm` files next to it.
3. Restore `media/`, if media is on the filesystem.
4. Start the app.

The FTS index (`catalog_fts`) is a table in the same database file, so it comes
back with the restore. If search returns nothing after a restore, rebuild it:

```bash
uv run python manage.py reindex
```

Check a restore by comparing the record count against what the source held,
opening a known record, and running a search that should return hits.


## Monitoring

### Health check

The app exposes a health check at `/health/`. It runs `SELECT 1` against the
database and returns:

- `200 {"status": "ok"}` when healthy.
- `503 {"status": "error", "detail": "..."}` when the database is unreachable.

The site password gate exempts the endpoint, so it answers without
authentication.

### Logs

Gunicorn writes access and error logs to stdout and stderr
(`--access-logfile -` and `--error-logfile -` in `entrypoint.sh`), where the
process manager or container runtime collects them. The application writes
its own log lines, and the traceback of any request that fails with a server
error, to the same stream with a timestamp, level and logger name.


## Troubleshooting

### Search returns nothing

Search reads the `catalog_fts` index rather than the record table, so
an empty index and an empty catalog look the same from the search
page.

Check whether the catalog holds records and the index does not:

```bash
uv run python manage.py shell -c "from catalog.models import Record; from django.db import connection; c = connection.cursor(); c.execute('select count(*) from catalog_fts'); print(Record.objects.count(), c.fetchone()[0])"
```

If the record count is non-zero and the index count is zero, run
`uv run python manage.py reindex`. Check the application logs for
`Could not index record` warnings, which name records the rebuild had
to skip.

### Database locked errors

SQLite is configured with WAL mode and a 5-second busy timeout
(`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`). Under normal use (2-3
concurrent catalogers), this is sufficient.

If "database is locked" errors appear:

- Check the application logs for concurrent write contention.
- Ensure only one instance of the app writes to the database. SQLite does not
  support multiple writers across machines.
- As a last resort, restart the app.

### Migration failures

If `migrate` fails:

- Check the logs for the specific error.
- Inspect the database directly with `uv run python manage.py dbshell`.
- If the migration is reversible, run
  `uv run python manage.py migrate <app> <previous_migration>` to roll back.
- If data is corrupted, restore from backup.

### API key issues (Anthropic)

If title page OCR fails with authentication errors:

- Verify `ANTHROPIC_API_KEY` is set in the environment the app runs in.
- Ensure the key has not been revoked or expired in the Anthropic dashboard.
- Check that `CLAUDE_MODEL` is set to a valid model name.

ISBN barcode scanning and manual entry do not require an API key.

### SRU endpoint failures

External catalog lookups may fail if upstream services are down or have changed
their URLs.

- Check the logs for connection errors or unexpected response codes.
- Test the endpoint directly:
  `curl "https://nli.alma.exlibrisgroup.com/view/sru/972NNL_INST?version=1.2&operation=searchRetrieve&query=alma.isbn=0123456789"`
- If an endpoint URL has changed, update the corresponding `SRU_*_URL`
  variable.

### Static files not loading

Static files are served by WhiteNoise and collected by `collectstatic`. If
styles or scripts are missing:

- The Tailwind build step in the Dockerfile may have failed. It runs
  before `collectstatic` and generates `static/css/tailwind.css`, which
  is not in the repository. Check the build logs.
- The `collectstatic` step in the Dockerfile may have failed. Check the build
  logs.
- Verify `STATIC_ROOT` points to `staticfiles/` in the project directory.

### Site password not working

The `SitePasswordMiddleware` reads `SITE_PASSWORD` at startup. Changing the
variable requires a restart to take effect. Clearing it disables the gate
entirely.
