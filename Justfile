# Development commands for otzar

# Recipes that serve or render a page depend on `tailwind`, so a fresh
# clone gets a styled application without anyone having to know that the
# stylesheet is generated. The build is a few hundred milliseconds once
# the CLI is cached, so running it every time costs less than the class
# of bug it removes.

# Start the development server
dev: tailwind
    uv run python manage.py runserver

# Run tests
test *args: tailwind
    uv run pytest {{args}}

# Lint check
lint:
    uv run ruff check .

# Lint with auto-fix
lint-fix:
    uv run ruff check --fix .

# Format code
fmt:
    uv run ruff format .

# Run database migrations
migrate:
    uv run python manage.py migrate

# Create new migrations
makemigrations *args:
    uv run python manage.py makemigrations {{args}}

# Open Django shell
shell:
    uv run python manage.py shell

# Create a superuser
createsuperuser:
    uv run python manage.py createsuperuser

# Run end-to-end browser tests
test-e2e *args: tailwind
    uv run pytest tests/e2e/ {{args}}

# Full pre-push check: format, lint, process labels, unit and e2e tests
check:
    ./scripts/check.sh

# Same, without the e2e suite
check-quick:
    ./scripts/check.sh --quick

# `--force` is not optional. Without it the command rebuilds only when
# static/src/input.css is newer than the output, and the classes that go
# stale are the ones a template added -- which that check never looks at.
# A full build takes about a second.

# Build Tailwind CSS from scratch
tailwind:
    uv run python manage.py tailwind build --force

# Load test/demo data
load-test-data:
    uv run python manage.py load_test_data

# Start dev server on LAN with HTTPS (for phone barcode scanning via QR code)
lan: tailwind
    #!/usr/bin/env bash
    IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
    CERT=tmp/cert.pem
    KEY=tmp/key.pem
    if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
        echo "Generating local SSL certs with mkcert..."
        mkdir -p tmp
        mkcert -cert-file "$CERT" -key-file "$KEY" localhost 127.0.0.1 "$IP"
    fi
    echo "Starting on https://$IP:8000"
    echo "Open this URL or scan the QR code from the scan page on your phone."
    ALLOWED_HOSTS="localhost,127.0.0.1,$IP" \
    CSRF_TRUSTED_ORIGINS="https://$IP:8000" \
    uv run python manage.py runserver_plus 0.0.0.0:8000 --cert-file "$CERT" --key-file "$KEY"

# Clean up old discarded scans
cleanup-staging days="30":
    uv run python manage.py cleanup_staging --days {{days}}
