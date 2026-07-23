from django.conf import settings


def site_context(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "APP_VERSION": settings.APP_VERSION,
        "current_year": __import__("datetime").datetime.now().year,
    }
