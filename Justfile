# Development commands for otzar

# Start the development server
dev:
    uv run python manage.py runserver

# Run tests
test *args:
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
test-e2e *args:
    uv run pytest tests/e2e/ {{args}}

# Full CI check: tests, lint, format
check:
    uv run pytest --ignore=tests/e2e
    uv run ruff check .
    uv run ruff format --check .

# Build Tailwind CSS
tailwind:
    uv run python manage.py tailwind build

# Load test/demo data
load-test-data:
    uv run python manage.py load_test_data

# Start dev server on LAN with HTTPS (for phone barcode scanning via QR code)
lan:
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
