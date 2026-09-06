FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Build the stylesheet. Tailwind derives it from the templates, so it is
# generated rather than committed, and the image has to produce its own.
# It belongs here rather than in the entrypoint: the templates are fixed
# once the image is built, so rebuilding at container start would repeat
# identical work, pull the Tailwind CLI down on every start, and give
# each container a different file timestamp -- which is what the
# stylesheet URL's cache-busting stamp is read from, so browsers would
# refetch unchanged CSS after every restart.
RUN uv run python manage.py tailwind build --force

# Collect static files (uses whitenoise, no volume needed)
RUN DATABASE_URL=sqlite:////tmp/throwaway.db \
    uv run python manage.py collectstatic --noinput

# Entrypoint handles migrations and starts gunicorn
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
