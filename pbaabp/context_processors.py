from django.conf import settings


def recaptcha_site_key(request):
    return {"recaptcha_site_key": settings.RECAPTCHA_PUBLIC_KEY}
