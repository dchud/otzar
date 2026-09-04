"""Template context every page needs."""

from django.conf import settings

from otzar.build_info import GITHUB_URL


def site_chrome(request):
    """Repository link and build identity for the header and footer.

    ``build_info`` is None when the running tree carries no git
    metadata, and the footer then shows no build line.
    """
    return {
        "github_url": GITHUB_URL,
        "build_info": settings.BUILD_INFO,
    }
