import os
from pathlib import Path

from dotenv import load_dotenv

from otzar import build_info

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Resolved here so it is read once per process, at startup. Shelling out
# to git during a render would pay a subprocess on every page for a
# value that cannot change while the process runs.
BUILD_INFO = build_info.resolve(BASE_DIR)

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-only-change-me")

DEBUG = os.environ.get("DEBUG", "true").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_tailwind_cli",
    "django_extensions",
    "catalog",
    "sources",
    "ingest",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Below WhiteNoise and above everything that writes a response body.
    #
    # Below WhiteNoise because WhiteNoise answers static requests itself
    # and never calls what follows it, so the files it already
    # compressed once at collect time are not compressed again on every
    # request. Above the rest because compression has to be the last
    # thing that happens to a body on the way out.
    #
    # On BREACH: compressing a response that carries a secret next to
    # attacker-supplied text leaks the secret through the response
    # length -- the attacker submits a guess, and a guess that matches
    # the secret compresses better than one that does not. Django masks
    # the CSRF token with a fresh random pad on every render, so the
    # token never appears twice as the same bytes and a guess has
    # nothing to compress against. Session identifiers travel in
    # cookies, not in bodies, so the same page carries no other secret
    # worth extracting. The pages here that mix user-supplied text with
    # a form -- search results, the catalogue, the ingest workflow --
    # are covered by that masking, so compression is safe.
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "otzar.middleware.SitePasswordMiddleware",
]

ROOT_URLCONF = "otzar.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "otzar.context_processors.site_chrome",
            ],
        },
    },
]

WSGI_APPLICATION = "otzar.wsgi.application"

# Root for persistent data: the SQLite database, the file-based cache
# and uploaded media all live under it. Point it at storage that
# outlives the process; defaults to the project directory.
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR))).resolve()

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": DATA_DIR / "cache",
    }
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Compress static files when they are collected, not when they are
# served. WhiteNoise writes a .gz (and a .br where brotli is available)
# beside each collected file and serves whichever the browser accepts,
# so the compiled stylesheet and the vendored HTMX and Alpine bundles --
# roughly 130 KB of text between them -- reach a phone at about a
# quarter of that, and the work is done once per build rather than once
# per request.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = DATA_DIR / "media"

TAILWIND_CLI_SRC_CSS = "static/src/input.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
