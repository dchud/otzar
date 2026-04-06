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

# Full CI check: tests, lint, format
check:
    uv run pytest
    uv run ruff check .
    uv run ruff format --check .

# Build Tailwind CSS
tailwind:
    uv run python manage.py tailwind build

# Load test/demo data
load-test-data:
    uv run python manage.py load_test_data

# Clean up old discarded scans
cleanup-staging days="30":
    uv run python manage.py cleanup_staging --days {{days}}
