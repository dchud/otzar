FROM python:3.13-slim

# Set by BuildKit to the architecture being built for: arm64 on Apple
# silicon, amd64 in CI and on the server. The legacy builder leaves it
# unset, and the build then asks dpkg, which answers in the same terms.
ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# `uv run` syncs the environment to the default groups before running,
# and `dev` is one of them, so without this any `uv run` in the image
# would install pytest, playwright and the rest. The entrypoint calls
# the virtualenv's executables directly and never syncs; this covers an
# operator's `uv run` inside the container.
ENV UV_NO_DEV=1
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Litestream, pinned by version and checksum. Release assets name the
# architectures x86_64 and arm64.
ARG LITESTREAM_VERSION=0.5.17
ARG LITESTREAM_SHA256_AMD64=cfb371176d164437ae869f8351cfde49bd1804ae71c61923f75c9cba9c9c006d
ARG LITESTREAM_SHA256_ARM64=f8ca4a050095c1efbda2c4365172e61bf9d955ea0d9ac42f448b52e51819baa5
RUN set -eu; \
    target="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    case "$target" in \
        amd64) arch=x86_64; sum="$LITESTREAM_SHA256_AMD64" ;; \
        arm64) arch=arm64; sum="$LITESTREAM_SHA256_ARM64" ;; \
        *) echo "no Litestream build for '$target'" >&2; exit 1 ;; \
    esac; \
    url="https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-${arch}.tar.gz"; \
    python -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' \
        "$url" /tmp/litestream.tar.gz; \
    echo "$sum  /tmp/litestream.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/litestream.tar.gz -C /usr/local/bin litestream; \
    rm /tmp/litestream.tar.gz; \
    litestream version

# Pinned so that rebuilding the same commit gets the same tool.
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

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
RUN python manage.py tailwind build --force

# Collect static files (uses whitenoise, no volume needed)
RUN python manage.py collectstatic --noinput

COPY entrypoint.sh /entrypoint.sh
COPY litestream-config.sh /usr/local/bin/litestream-config
RUN chmod +x /entrypoint.sh /usr/local/bin/litestream-config

# The commit the image was built from, for the footer and the snapshot
# manifest; .git is not in the build context. Declared after the build
# steps so that a new value does not invalidate their cached layers.
# Unset, the image reports no commit.
ARG GIT_COMMIT=
ENV GIT_COMMIT=$GIT_COMMIT

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
