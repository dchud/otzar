from django.conf import settings


def test_settings_loaded():
    """Django settings module can be loaded."""
    assert settings.configured


def test_catalog_in_installed_apps():
    assert "catalog" in settings.INSTALLED_APPS


def test_sources_in_installed_apps():
    assert "sources" in settings.INSTALLED_APPS


def test_ingest_in_installed_apps():
    assert "ingest" in settings.INSTALLED_APPS
