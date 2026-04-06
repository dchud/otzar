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
