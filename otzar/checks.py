from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security)
def check_site_password(app_configs, **kwargs):
    """Warn when a production configuration leaves the site open.

    A warning rather than an error: a public catalog is a legitimate
    configuration, but it should be a deliberate one.
    """
    if settings.DEBUG or settings.SITE_PASSWORD:
        return []
    return [
        Warning(
            "SITE_PASSWORD is empty and DEBUG is false, so every page "
            "and both login forms are open to anyone.",
            hint="Set SITE_PASSWORD in the environment, unless the "
            "catalog is meant to be public.",
            id="otzar.W001",
        )
    ]
