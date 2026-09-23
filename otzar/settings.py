import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from otzar import build_info

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Resolved here so it is read once per process, at startup. Shelling out
# to git during a render would pay a subprocess on every page for a
# value that cannot change while the process runs.
BUILD_INFO = build_info.resolve(BASE_DIR)

_DEV_SECRET_KEY = "django-insecure-dev-only-change-me"

# An empty SECRET_KEY= line in .env reads as "", which falls back the
# same way an absent one does.
SECRET_KEY = os.environ.get("SECRET_KEY") or _DEV_SECRET_KEY

DEBUG = os.environ.get("DEBUG", "true").lower() in ("true", "1", "yes")

# The fallback is published in this file, so a production process
# running on it signs sessions and CSRF tokens with a key anyone can
# read. Refuse to start rather than run that way.
if not DEBUG and SECRET_KEY == _DEV_SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is false.")

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
    "axes",
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
    # Last, as django-axes requires: it turns a lockout raised during
    # authentication into the lockout response.
    "axes.middleware.AxesMiddleware",
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

TAILWIND_CLI_SRC_CSS = "assets/input.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

AUTHENTICATION_BACKENDS = [
    # First, so a locked-out username and address are refused before
    # any password is checked.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Login throttling, on both the site login and the admin login. A
# lockout is keyed on the username and the client address together, so
# one person mistyping locks out that username from that address only,
# not everyone behind the same address and not the same account
# elsewhere. A successful login clears the count. `manage.py
# axes_reset` clears a lockout by hand.
AXES_FAILURE_LIMIT = 5
# templates/registration/lockout.html states this period; change both.
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/lockout.html"
AXES_CLIENT_IP_CALLABLE = "otzar.client_ip.client_ip"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Django merges DEFAULT_LOGGING (django/utils/log.py) with this dict
# rather than replacing it: it runs dictConfig(DEFAULT_LOGGING), then
# dictConfig(LOGGING). DEFAULT_LOGGING defines a "django" logger with
# its own console handler (active only while DEBUG is true) and a
# mail_admins handler; both are left alone here. The application
# loggers below attach their own console handler directly instead of
# going through a shared root handler, because a root handler would
# also catch everything that already propagates there from "django",
# printing Django's own log lines a second time.
#
# disable_existing_loggers is set here (not just left at DEFAULT_LOGGING's
# False) because dictConfig defaults it to True on every call, including
# this one -- without an explicit False, any logger already created
# before this dict is applied and not named in "loggers" below,
# including "django" and "django.server", would be disabled.
_APP_LOG_LEVEL = "DEBUG" if DEBUG else "INFO"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "loggers": {
        # catalog, ingest and sources cover every application module by
        # prefix -- a logger named "sources.marc" is a child of
        # "sources" and inherits this level and handler unless it sets
        # its own. propagate is False so a record reaching this
        # handler does not also climb to root and print twice.
        "catalog": {
            "handlers": ["console"],
            "level": _APP_LOG_LEVEL,
            "propagate": False,
        },
        "ingest": {
            "handlers": ["console"],
            "level": _APP_LOG_LEVEL,
            "propagate": False,
        },
        "sources": {
            "handlers": ["console"],
            "level": _APP_LOG_LEVEL,
            "propagate": False,
        },
        # Django's own "django" logger has a console handler in
        # DEFAULT_LOGGING, but it carries require_debug_true, so with
        # DEBUG false a request traceback goes only to mail_admins,
        # which is not configured. Naming "django" here replaces that
        # configuration, so tracebacks reach stdout in production.
        # "django.request" is where unhandled exceptions are logged;
        # it propagates to "django" and needs no handler of its own.
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # httpx logs one line per request at INFO and its own request
        # internals at DEBUG; the SRU cascade makes several calls per
        # lookup, so this stays at WARNING regardless of DEBUG.
        # httpcore is the transport httpx logs through underneath it.
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    },
}

# Production sits behind a reverse proxy that terminates TLS, so Django
# sees plain HTTP. These apply whenever DEBUG is false; local
# development keeps plain-http cookies and no HSTS.
if not DEBUG:
    # Trust the proxy's X-Forwarded-Proto. This is safe only because
    # gunicorn is reachable from nothing but the proxy: the container
    # publishes its port on the host's loopback interface. On a host
    # where gunicorn answers directly, a client could send this header
    # itself and be treated as having arrived over https.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # An hour: long enough to satisfy the check, short enough that a
    # mistake in the TLS setup locks browsers out for an hour rather
    # than a year. Raise it once the site has served https without
    # incident.
    SECURE_HSTS_SECONDS = 3600
    # Caddy redirects http to https before a request reaches Django,
    # so SECURE_SSL_REDIRECT stays off and check --deploy's W008 is
    # expected. So are W005 and W021: HSTS covers this host only, not
    # its subdomains, and the site is not submitted for preloading.
