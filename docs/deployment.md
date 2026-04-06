# Deployment guide

This document covers deploying and operating otzar on Fly.io.

## Prerequisites

- **flyctl CLI** installed (`brew install flyctl` or see
  https://fly.io/docs/flyctl/install/)
- A **Fly.io account** (`fly auth login`)
- A **GitHub repository** with Actions enabled (for continuous deployment)
- Docker (flyctl builds remotely by default, but local Docker is useful for
  testing)

## Initial setup

### Create the app

```sh
fly launch --name otzar --region iad --no-deploy
```

This creates the app in the Ashburn (iad) region without deploying immediately.
The generated `fly.toml` is already checked into the repository. If `fly launch`
overwrites it, restore the checked-in version.

### Create the persistent volume

```sh
fly volumes create appdata --region iad --size 1
```

This creates a 1 GB NVMe volume named `appdata`. The volume is mounted at
`/data` inside the container (configured in `fly.toml`). SQLite databases
and media files live here. The volume persists across deploys.

### Machine size

The app runs on a `shared-cpu-1x` VM with 512 MB RAM, configured in `fly.toml`.
This is sufficient for a small community catalog. Adjust with `fly scale` if
needed.

## Secrets

Set required secrets before the first deploy:

```sh
fly secrets set \
  SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" \
  ANTHROPIC_API_KEY="sk-ant-..." \
  ALLOWED_HOSTS="otzar.fly.dev" \
  CSRF_TRUSTED_ORIGINS="https://otzar.fly.dev"
```

Optional secrets:

```sh
fly secrets set SITE_PASSWORD="..."          # site-wide password gate
fly secrets set AWS_ACCESS_KEY_ID="..."      # for Litestream S3 backups
fly secrets set AWS_SECRET_ACCESS_KEY="..."
fly secrets set AWS_S3_BUCKET="..."
fly secrets set AWS_S3_REGION="us-east-1"
```

To list current secrets (names only, not values):

```sh
fly secrets list
```

Environment variables that are not secrets (like `DEBUG=false`, `PORT=8000`,
`DATA_DIR=/data`) are set in the `[env]` section of `fly.toml` and do not need
`fly secrets set`.

## First deploy

### Deploy the app

```sh
fly deploy
```

This builds the Docker image remotely using the `Dockerfile`, pushes it to
Fly.io's registry, and starts the machine. The entrypoint script
(`entrypoint.sh`) runs migrations automatically before starting gunicorn.

### Create a superuser

After the first deploy succeeds:

```sh
fly ssh console -C "uv run python manage.py createsuperuser"
```

Follow the interactive prompts to set the admin username, email, and password.

### Verify

```sh
fly status          # check machine is running
fly open            # open the app URL in your browser
```

The health check endpoint at `/health/` is polled automatically by Fly.io every
30 seconds.

## GitHub Actions continuous deployment

The repository includes a deploy workflow at `.github/workflows/deploy.yml`.
On every push to `main`, it:

1. Runs tests (`uv run pytest`)
2. Runs linting (`uv run ruff check .`)
3. Runs format check (`uv run ruff format --check .`)
4. If all pass, deploys to Fly.io (`flyctl deploy --remote-only`)

### Setup

1. Generate a Fly.io deploy token:

   ```sh
   fly tokens create deploy
   ```

2. Add it as a GitHub repository secret named `FLY_API_TOKEN`:
   - Go to the repository on GitHub
   - Settings > Secrets and variables > Actions
   - New repository secret: name `FLY_API_TOKEN`, value is the token from
     step 1

The workflow uses `concurrency: deploy` to prevent simultaneous deploys.

## Routine operations

### Deploying updates

Push to `main`. GitHub Actions runs tests and deploys automatically. No manual
steps needed for routine code changes.

For an urgent deploy bypassing CI:

```sh
fly deploy --remote-only
```

### Running management commands

```sh
fly ssh console -C "uv run python manage.py <command>"
```

Examples:

```sh
fly ssh console -C "uv run python manage.py createsuperuser"
fly ssh console -C "uv run python manage.py migrate --list"
fly ssh console -C "uv run python manage.py shell"
```

For an interactive shell session:

```sh
fly ssh console
```

### Checking logs

```sh
fly logs              # stream live logs
fly logs --app otzar  # specify app name if needed
```

Gunicorn access and error logs are written to stdout/stderr and captured by
Fly.io's log system.

## Backups

### Fly.io volume snapshots

Fly.io takes daily snapshots of persistent volumes automatically. These capture
the entire volume including the SQLite database and media files.

To list snapshots:

```sh
fly volumes list
fly volumes snapshots list <volume-id>
```

Snapshot retention defaults to 5 days. To increase retention (up to 60 days),
configure it in `fly.toml`:

```toml
[mounts]
  source = "appdata"
  destination = "/data"
  snapshot_retention = 30
```

Then redeploy for the change to take effect.

### Litestream (continuous SQLite backup to S3)

Litestream streams SQLite WAL changes to an S3 bucket in near-real-time,
providing point-in-time recovery between daily volume snapshots.

Setup:

1. Create an S3 bucket (or compatible object storage) for backups.
2. Create an IAM user with write access to the bucket.
3. Set the AWS secrets on the Fly.io app (see Secrets section above).
4. Add Litestream to the Docker image and configure it in `entrypoint.sh` to
   run alongside gunicorn, replicating the SQLite database at
   `/data/db.sqlite3` to the S3 bucket.

Litestream configuration (typically `/etc/litestream.yml`):

```yaml
dbs:
  - path: /data/db.sqlite3
    replicas:
      - type: s3
        bucket: ${AWS_S3_BUCKET}
        path: otzar/db
        region: ${AWS_S3_REGION}
        access-key-id: ${AWS_ACCESS_KEY_ID}
        secret-access-key: ${AWS_SECRET_ACCESS_KEY}
```

Verify replication is working:

```sh
fly ssh console -C "litestream snapshots /data/db.sqlite3"
```

Note: Litestream backs up the SQLite database only, not media files. Media
files are covered by Fly.io volume snapshots.

## Restore procedures

### Restore from a Fly.io volume snapshot

Use this when the volume is lost or corrupted.

1. List available snapshots:

   ```sh
   fly volumes list
   fly volumes snapshots list <volume-id>
   ```

2. Create a new volume from a snapshot:

   ```sh
   fly volumes create appdata --region iad --size 1 --snapshot-id <snapshot-id>
   ```

3. If the old volume still exists, delete it:

   ```sh
   fly volumes delete <old-volume-id>
   ```

4. Redeploy to attach the new volume:

   ```sh
   fly deploy
   ```

### Restore from Litestream

Use this when you need to recover the database to a specific point in time or
when volume snapshots are too old.

1. SSH into the running machine (or a temporary one):

   ```sh
   fly ssh console
   ```

2. Stop the application (or use a fresh machine with the volume attached).

3. Restore the database:

   ```sh
   litestream restore -o /data/db.sqlite3 s3://<bucket>/otzar/db
   ```

4. Restart the application:

   ```sh
   fly apps restart
   ```

Litestream restores the database only. Media files must be recovered from a
volume snapshot if also lost.

## Rollback

To revert to a previous deployment:

1. List recent deployments to find the previous image:

   ```sh
   fly releases
   ```

2. Redeploy with the previous image:

   ```sh
   fly deploy --image <previous-image-ref>
   ```

This reverts the application code but does not undo database migrations. If a
migration was destructive (which should never happen per project policy), restore
the database from Litestream or a volume snapshot before rolling back the code.

## Monitoring

### Health check

The `/health/` endpoint is checked by Fly.io every 30 seconds (configured in
`fly.toml`). A 200 response means the app is running and can serve requests.
The health check has a 10-second grace period on startup to allow migrations
to complete.

### Status and logs

```sh
fly status    # machine state, IP addresses, health check results
fly logs      # live log stream
```

### External monitoring

For uptime alerting beyond Fly.io's built-in checks, use a service like
UptimeRobot or Healthchecks.io pointing at `https://otzar.fly.dev/health/`.

## Cost estimate

Estimated monthly cost on Fly.io (as of early 2026):

| Resource               | Cost       |
|------------------------|------------|
| shared-cpu-1x, 512 MB  | ~$3.00     |
| 1 GB persistent volume | ~$0.15     |
| Outbound transfer      | ~$0.00*    |
| **Total (Fly.io)**     | **~$3.15** |

*Fly.io includes a free allowance for outbound transfer that a small catalog
is unlikely to exceed.

Additional costs outside Fly.io:

- **S3 storage for Litestream backups**: negligible for a small SQLite database
  (under $0.10/month).
- **Claude Vision API** (for title page OCR): ~$0.02 per image with Sonnet.
  Varies with cataloging activity.

The `auto_stop_machines = "stop"` setting in `fly.toml` stops the machine when
idle and restarts it on incoming requests, which can reduce costs further if
the app has periods of inactivity. `min_machines_running = 1` keeps at least
one machine running to avoid cold-start latency.
