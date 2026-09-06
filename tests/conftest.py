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

    That is not a hypothetical. Removing this fixture makes
    ``test_search_by_author_cascades_on_empty`` fail, because its first
    cascade query is one an earlier test in the same module has already
    put in the cache -- so the request it expects never leaves.

    The fixture belongs here rather than beside a single test module
    because the ordering it defends against runs across modules, and the
    test it rescues is not one of the ones that added the caching.
    ``tests/e2e/`` inherits it as a subdirectory.

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
