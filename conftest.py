import pytest
from django.core.cache import cache
from django.test import override_settings


@pytest.fixture(autouse=True)
def isolated_response_cache():
    """Give every test its own empty cache.

    ``sources.cache.ResponseCache`` is backed by Django's default cache,
    which this project configures as a file cache under ``DATA_DIR``. The
    SRU and VIAF clients consult it before issuing a request, so without
    isolation a response stored by one test would be served to the next:
    a test asserting on request counts would pass or fail depending on
    what ran before it, and running the suite would write into the
    developer's real cache directory.

    Swapping in a per-test locmem backend removes both problems. The
    override is what makes the ordering guarantee; the clears defend
    against a locmem instance being reused across tests for the same
    LOCATION.
    """
    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "otzar-test-response-cache",
            }
        }
    ):
        cache.clear()
        yield
        cache.clear()
