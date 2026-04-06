# Administration guide

System administration reference for the otzar catalog application.

## Configuration reference

All configuration is via environment variables, loaded from a `.env` file locally or set as Fly.io secrets in production. See `.env.example` for a template.

### Django core

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes (production) | Insecure dev fallback | Django secret key. Generate with: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | No | `true` | Set to `false` in production. Accepts `true`, `1`, `yes` (case-insensitive). |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated list of hostnames the app will serve. In production, set to `otzar.fly.dev` and any custom domain. |
| `CSRF_TRUSTED_ORIGINS` | No | (empty) | Comma-separated list of origins for CSRF validation. Set to the full production URL (e.g. `https://otzar.fly.dev`). |
| `DATA_DIR` | No | Project root | Directory for the SQLite database, cache, and media files. On Fly.io, set to `/data` (the mounted persistent volume). Locally, defaults to the project directory. |

### Claude Vision OCR

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | For title page scanning | (none) | Anthropic API key. Required only if using title page photograph/OCR ingest. Not needed for ISBN scan or manual entry. |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-6` | Model used for OCR. Sonnet is recommended for Hebrew script accuracy. |

### S3 backups

Required in production for Litestream continuous backups. Not needed for local development.

| Variable | Required | Default | Description |
|---|---|---|---|
| `AWS_ACCESS_KEY_ID` | Production | (none) | AWS access key for the S3 backup bucket. |
| `AWS_SECRET_ACCESS_KEY` | Production | (none) | AWS secret key. |
| `AWS_S3_BUCKET` | Production | (none) | S3 bucket name for WAL streaming. |
| `AWS_S3_REGION` | No | `us-east-1` | AWS region for the backup bucket. |

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

Cataloger accounts are standard Django user accounts. Create them in one of two ways:

**Via Django admin** (preferred for ongoing use): Log in at `/admin/`, go to Users, and add a new user. Staff status is not required for cataloging; any authenticated user can access ingest features.

**Via command line** (initial setup):

```bash
uv run python manage.py createsuperuser
# or with just:
just createsuperuser
```

### Setting or clearing the site-wide password

The site-wide password is controlled entirely by the `SITE_PASSWORD` environment variable.

- **Set it**: Add `SITE_PASSWORD=yourpassword` to `.env` (local) or `fly secrets set SITE_PASSWORD=yourpassword` (production). The app reads this at startup.
- **Clear it**: Remove the variable or set it to an empty string. Restart the app (or redeploy) for the change to take effect.

When active, unauthenticated visitors see a password prompt. Once entered correctly, the password is stored in the session. Logged-in catalogers bypass the gate entirely.

### Loading test data

Populates the database with representative sample records for development or demos:

```bash
uv run python manage.py load_test_data
# or:
just load-test-data
```

This creates sample authors, publishers, subjects, series, locations, and catalog records. It uses `get_or_create` and is safe to run multiple times.


## Management commands

### `load_test_data`

Loads representative test data (authors, records, series, locations) for development and demos.

```bash
uv run python manage.py load_test_data
```

No arguments. Uses `get_or_create`, so running it again does not duplicate data.

### `cleanup_staging`

Deletes old discarded scan results and orphaned staging images.

```bash
uv run python manage.py cleanup_staging [--days N]
```

| Option | Default | Description |
|---|---|---|
| `--days` | 30 | Retention period in days. Discarded `ScanResult` records older than this and staging image files older than this are deleted. |

This removes:
1. `ScanResult` objects with status `discarded` where `updated_at` is older than the cutoff.
2. Image files in `tmp/title_pages/` with filesystem modification times older than the cutoff.

Run periodically (e.g. weekly via cron or a scheduled Fly.io machine) to reclaim storage.


## Backup and restore

### Fly.io volume snapshots

Fly.io takes daily snapshots of the persistent volume (`/data`), which contains the SQLite database, cache, and media files. Snapshots are retained for up to 60 days.

List snapshots:

```bash
fly volumes list
fly volumes snapshots list <volume-id>
```

Restore from a snapshot by creating a new volume from it and redeploying. See `docs/deployment.md` for the full procedure.

### Litestream

Litestream continuously streams SQLite WAL changes to S3. This provides point-in-time recovery beyond what daily snapshots offer.

Litestream requires the `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_S3_BUCKET` environment variables to be set.

To restore from Litestream:

1. Stop the app: `fly machine stop`
2. SSH into the machine: `fly ssh console`
3. Restore the database: `litestream restore -o /data/db.sqlite3 s3://<bucket>/db.sqlite3`
4. Restart the app: `fly machine start`

### Media files

Media files (title page images) are stored on the persistent volume under `/data/media/`. They are included in volume snapshots but not in Litestream backups (which cover only the SQLite database).


## Monitoring

### Health check

The app exposes a health check at `/health/`. It runs `SELECT 1` against the database and returns:

- `200 {"status": "ok"}` when healthy.
- `503 {"status": "error", "detail": "..."}` when the database is unreachable.

Fly.io polls this endpoint every 30 seconds (configured in `fly.toml`).

### Logs

View application logs:

```bash
fly logs                   # live tail
fly logs --app otzar       # explicit app name
```

Gunicorn access logs and error logs are written to stdout/stderr and captured by Fly.io.

### Status

```bash
fly status                 # machine state, region, image version
fly volumes list           # volume health and size
fly checks list            # health check history
```


## Upgrading

### How updates are applied

The project uses continuous deployment via GitHub Actions. Pushing to `main` triggers:

1. Tests run in CI.
2. On success, the app is built as a Docker image and deployed to Fly.io.
3. The entrypoint script runs `manage.py migrate --noinput` before starting gunicorn, so database migrations are applied automatically on each deploy.

### After a deploy

Check that the app is healthy:

```bash
fly status
curl https://otzar.fly.dev/health/
fly logs  # check for migration errors or startup issues
```

### Rollback

If a deploy causes problems:

1. **Redeploy the previous image**: `fly deploy --image <previous-image-ref>`. Find previous image references in the Fly.io dashboard or GitHub Actions logs.
2. **Restore the database**: If a migration caused data issues, restore from a Litestream backup or volume snapshot (see Backup and restore above).

Migrations are designed to be non-destructive. Review each migration before merging to `main`.


## Troubleshooting

### Database locked errors

SQLite is configured with WAL mode and a 5-second busy timeout (`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`). Under normal use (2-3 concurrent catalogers), this is sufficient.

If "database is locked" errors appear:
- Check `fly logs` for concurrent write contention.
- Ensure only one Fly.io machine is running (`fly scale show`). SQLite does not support multiple writers across machines.
- As a last resort, restart the machine: `fly machine restart`.

### Migration failures

If `migrate` fails during deploy:
- Check `fly logs` for the specific error.
- SSH into the machine (`fly ssh console`) and inspect the database state.
- If the migration is reversible, run `uv run python manage.py migrate <app> <previous_migration>` to roll back.
- If data is corrupted, restore from backup.

### API key issues (Anthropic)

If title page OCR fails with authentication errors:
- Verify `ANTHROPIC_API_KEY` is set: `fly secrets list` (it will show the key name but not the value).
- Ensure the key has not been revoked or expired in the Anthropic dashboard.
- Check that `CLAUDE_MODEL` is set to a valid model name.

ISBN barcode scanning and manual entry do not require an API key.

### SRU endpoint failures

External catalog lookups may fail if upstream services are down or have changed their URLs.
- Check `fly logs` for connection errors or unexpected response codes.
- Test the endpoint directly: `curl "https://nli.alma.exlibrisgroup.com/view/sru/972NNL_INST?version=1.2&operation=searchRetrieve&query=alma.isbn=0123456789"`
- If an endpoint URL has changed, update the corresponding `SRU_*_URL` secret.

### Static files not loading

Static files are served by WhiteNoise and collected at build time. If styles or scripts are missing after a deploy:
- The `collectstatic` step in the Dockerfile may have failed. Check the build logs.
- Verify `STATIC_ROOT` points to `staticfiles/` in the project directory.

### Site password not working

The `SitePasswordMiddleware` reads `SITE_PASSWORD` at startup. Changes to the secret require a restart or redeploy to take effect. Clearing the variable disables the gate entirely.
