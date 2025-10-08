from pathlib import Path

import environ

env = environ.Env()

SENTRY_DSN = env("SENTRY_DSN", default=None)

if SENTRY_DSN is not None:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        send_default_pii=True,
    )

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(BASE_DIR / ".env")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-l+*3%+le)@z#dwiv5x7(kw#hp&qqa$tkzf)gdm%%e)m^02c5w6",
)
SECRET_KEY_FALLBACKS = env.list("DJANGO_SECRET_KEY_FALLBACKS", default=[])

APPEND_SLASH = True

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=False)
THUMBNAIL_DEBUG = DEBUG

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=["http://localhost"])
SITE_URL = env("DJANGO_SITE_URL", default="http://localhost:8000")

CORS_URLS_REGEX = r"^/lazer/.*$"
CORS_ALLOW_ALL_ORIGINS = True

DATA_UPLOAD_MAX_MEMORY_SIZE = env("DATA_UPLOAD_MAX_MEMORY_SIZE", default=2621440)
FILE_UPLOAD_MAX_MEMORY_SIZE = env("FILE_UPLOAD_MAX_MEMORY_SIZE", default=2621440)

# Application definition

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    # Wagtail
    "wagtail_localize",
    "wagtail_localize_git",
    "wagtail_localize.locales",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.routable_page",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtailset.draftail_anchors",
    "wagtail.contrib.table_block",
    "wagtail",
    "modelcluster",
    "taggit",
    # Wagtail Addons
    "wagtail_link_block",
    # Addons
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.discord",
    "corsheaders",
    "django_bleach",
    "django_htmx",
    "django_recaptcha",
    "djstripe",
    "email_log",
    "markdownfield",
    "ordered_model",
    "sitetree",
    "django_tuieditor",
    "csvexport",
    "markdownify.apps.MarkdownifyConfig",
    "leaflet",
    "easy_thumbnails",
    "qr_code",
    "admin_extra_buttons",
    # Our apps
    "pbaabp",
    "pages",
    "membership",
    "profiles",
    "events",
    "neighborhood_selection",
    "campaigns",
    "release",
    "maillinks",
    "facets",
    "projects",
    "organizers",
    "aliases",
    "lazer",
    "cms",
    "elections",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "pbaabp.middleware.TimezoneMiddleware",
    "pbaabp.middleware.FooterNewsletterSignupFormMiddleware",
]

ROOT_URLCONF = "pbaabp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "pbaabp.wsgi.application"
ASGI_APPLICATION = "pbaabp.asgi.application"

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"
DATABASES["default"]["ATOMIC_REQUESTS"] = True
CONN_MAX_AGE = env.int("DJANGO_CONN_MAX_AGE", default=600)
if CONN_MAX_AGE:
    DATABASES["default"]["CONN_MAX_AGE"] = CONN_MAX_AGE
CONN_HEALTH_CHECKS = env.bool("DJANGO_CONN_HEALTH_CHECKS", default=True)
if CONN_HEALTH_CHECKS:
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = CONN_HEALTH_CHECKS

# Speed up tests by skipping migrations and creating schema directly from models
DATABASES["default"]["TEST"] = {
    "MIGRATE": False,
}

_REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
if _REDIS_URL.startswith("rediss://"):
    _REDIS_URL = _REDIS_URL + "?ssl_cert_reqs=none"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

if True:
    CACHES["default"]["BACKEND"] = "django_redis.cache.RedisCache"
    CACHES["default"]["LOCATION"] = f"{_REDIS_URL}/10"
    CACHES["default"]["OPTIONS"] = {"CLIENT_CLASS": "django_redis.client.DefaultClient"}


# Authentication
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    "sesame.backends.ModelBackend",
]


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "America/New_York"

USE_I18N = True
LOCALE_PATHS = [
    "locale",
]

WAGTAIL_I18N_ENABLED = True
WAGTAIL_CONTENT_LANGUAGES = LANGUAGES = [
    ("en", "English"),
    ("es", "Spanish"),
]

if not DEBUG:
    WAGTAILLOCALIZE_GIT_URL = "git@github.com:PhillyBikeAction/apps-bikeaction-org-content-pos.git"
    WAGTAILLOCALIZE_GIT_CLONE_DIR = "/data/translations/wagtail-content-pos.git"

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

THUMBNAIL_ALIASES = {
    "campaigns.Campaign.cover": {
        "small": {"size": (512, 0), "quality": 100},
        "banner": {"size": (1768, 0), "quality": 90},
    },
}

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default=None)
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default=None)
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default=None)
AWS_DEFAULT_ACL = "public-read"
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default=None)
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)

if all(
    [x is not None for x in [AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME]]
):
    STORAGES["default"] = {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}
    THUMBNAIL_DEFAULT_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = _REDIS_URL
CELERY_RESULT_BACKEND = _REDIS_URL
CELERY_BEAT_SCHEDULE = {}

# MAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-subject-prefix
EMAIL_SUBJECT_PREFIX = env("DJANGO_EMAIL_SUBJECT_PREFIX", default="[Philly Bike Action]")

MAILGUN_EMAIL = env("MAILGUN_EMAIL", default=None)
MAILGUN_API_KEY = env("MAILGUN_API_KEY", default=None)
if MAILGUN_API_KEY is not None and MAILGUN_EMAIL is not None:
    print("sending email via mailgun api")
    EMAIL_BACKEND = "email_log.backends.EmailBackend"
    EMAIL_LOG_BACKEND = "anymail.backends.mailgun.EmailBackend"
    ANYMAIL = {"MAILGUN_API_KEY": MAILGUN_API_KEY}
else:
    print("sending email via smtp")
    EMAIL_BACKEND = "email_log.backends.EmailBackend"
    EMAIL_LOG_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="smtp.mailgun.org")
    EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=587)
    EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=True)
    EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default=None)
    EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default=None)


# https://docs.djangoproject.com/en/dev/ref/settings/#default-from-email
DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL", default="Philly Bike Action <noreply@bikeaction.org>"
)
# https://docs.djangoproject.com/en/dev/ref/settings/#server-email
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Wagtail
WAGTAIL_SITE_NAME = "Philly Bike Action!"

# Discord
DISCORD_BOT_TOKEN = env("DISCORD_BOT_TOKEN", default=None)

# Wordpress
WP_URL = env("WP_URL", default="https://bikeaction.org")
WP_LOGIN_EMAIL = env("WP_LOGIN_EMAIL", default=None)
WP_LOGIN_PASS = env("WP_LOGIN_PASS", default=None)
WP_CAMPAIGN_PAGE_ID = env("WP_CAMPAIGN_PAGE_ID", default=5877)

# Mailjet
MAILJET_API_KEY = env("MAILJET_API_KEY", default=None)
MAILJET_SECRET_KEY = env("MAILJET_SECRET_KEY", default=None)
MAILJET_CONTACT_LIST_ID = env("MAILJET_CONTACT_LIST_ID", default=None)
MAILJET_WEBHOOK_SECRET = env("MAILJET_WEBHOOK_SECRET", default=None)
MAILJET_SECRET_SIGNUP_URL = env("MAILJET_SECRET_SIGNUP_URL", default=None)

# django-allauth
ACCOUNT_FORMS = {
    "signup": "profiles.forms.ProfileSignupForm",
    "reset_password": "pbaabp.forms.CaptchaResetPasswordForm",
}
ACCOUNT_ADAPTER = "profiles.adapters.AccountAdapter"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http" if DEBUG else "https"
SOCIALACCOUNT_ADAPTER = "profiles.adapters.SocialAccountAdapter"
SOCIALACCOUNT_PROVIDERS = {
    "discord": {
        "APPS": [
            {
                "client_id": env("DISCORD_OAUTH_CLIENT_ID", default=None),
                "secret": env("DISCORD_OAUTH_CLIENT_SECRET", default=None),
                "key": "",
            }
        ],
    }
}

# django-sesame
SESAME_MAX_AGE = 7 * 24 * 3600

# django-recaptcha
if DEBUG:
    SILENCED_SYSTEM_CHECKS = ["django_recaptcha.recaptcha_test_key_error"]
    # https://developers.google.com/recaptcha/docs/faq#id-like-to-run-automated-tests-with-recaptcha.-what-should-i-do
    RECAPTCHA_PUBLIC_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
    RECAPTCHA_PRIVATE_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
else:
    RECAPTCHA_PUBLIC_KEY = env("RECAPTCHA_PUBLIC_KEY", default=None)
    RECAPTCHA_PRIVATE_KEY = env("RECAPTCHA_PRIVATE_KEY", default=None)

# dj-stripe
STRIPE_LIVE_SECRET_KEY = env("STRIPE_LIVE_SECRET_KEY", default=None)
STRIPE_LIVE_PUBLIC_KEY = env("STRIPE_LIVE_PUBLIC_KEY", default=None)
STRIPE_TEST_SECRET_KEY = env("STRIPE_TEST_SECRET_KEY", default=None)
STRIPE_TEST_PUBLIC_KEY = env("STRIPE_TEST_PUBLIC_KEY", default=None)
STRIPE_SECRET_KEY = STRIPE_TEST_SECRET_KEY if DEBUG else STRIPE_LIVE_SECRET_KEY
STRIPE_PUBLIC_KEY = STRIPE_TEST_PUBLIC_KEY if DEBUG else STRIPE_LIVE_PUBLIC_KEY
STRIPE_LIVE_MODE = not DEBUG
DJSTRIPE_USE_NATIVE_JSONFIELD = True
DJSTRIPE_WEBHOOK_SECRET = env("DJSTRIPE_WEBHOOK_SECRET", default=None)
DJSTRIPE_FOREIGN_KEY_TO_FIELD = "id"

# Events
EVENTS_HIDDEN_DISCORD_CHANNELS = env.list("EVENTS_HIDDEN_DISCORD_CHANNELS", default=[], cast=int)

# Neighborhood Selection
NEIGHBORHOOD_SELECTION_DISCORD_GUILD_ID = env(
    "NEIGHBORHOOD_SELECTION_DISCORD_GUILD_ID", default=None
)
NEIGHBORHOOD_SELECTION_DISCORD_CHANNEL_ID = env(
    "NEIGHBORHOOD_SELECTION_DISCORD_CHANNEL_ID", default=None
)
NEIGHBORHOOD_SELECTION_NOTIFICATION_DISCORD_CHANNEL_ID = env(
    "NEIGHBORHOOD_SELECTION_NOTIFICATION_DISCORD_CHANNEL_ID", default=None
)

# New Project Application Notifications
NEW_PROJECT_REVIEW_DISCORD_GUILD_ID = env("NEW_PROJECT_REVIEW_DISCORD_GUILD_ID", default=None)
NEW_PROJECT_REVIEW_DISCORD_CHANNEL_ID = env("NEW_PROJECT_REVIEW_DISCORD_CHANNEL_ID", default=None)
ACTIVE_PROJECT_CATEGORY_ID = env("ACTIVE_PROJECT_CATEGORY_ID", default=None)
ARCHIVED_PROJECT_CATEGORY_ID = env("ARCHIVED_PROJECT_CATEGORY_ID", default=None)
ACTIVE_PROJECT_LEAD_ROLE_ID = env("ACTIVE_PROJECT_LEAD_ROLE_ID", default=None)
PROJECT_LOG_CHANNEL_ID = env("PROJECT_LOG_CHANNEL_ID", default=None)
NEW_PROJECT_REVIEW_DISCORD_ROLE_MENTION_ID = env(
    "NEW_PROJECT_REVIEW_DISCORD_ROLE_MENTION_ID", default=None
)
NEW_PROJECT_REVIEW_DISCORD_VOTE_CHANNEL_ID = env(
    "NEW_PROJECT_REVIEW_DISCORD_VOTE_CHANNEL_ID", default=None
)
NEW_PROJECT_REVIEW_DISCORD_ROLE_VOTE_MENTION_ID = env(
    "NEW_PROJECT_REVIEW_DISCORD_ROLE_VOTE_MENTION_ID", default=None
)

# New Project Application Notifications
NEW_ORGANIZER_REVIEW_DISCORD_GUILD_ID = env("NEW_ORGANIZER_REVIEW_DISCORD_GUILD_ID", default=None)
NEW_ORGANIZER_REVIEW_DISCORD_CHANNEL_ID = env(
    "NEW_ORGANIZER_REVIEW_DISCORD_CHANNEL_ID", default=None
)
NEW_ORGANIZER_REVIEW_DISCORD_ROLE_MENTION_ID = env(
    "NEW_ORGANIZER_REVIEW_DISCORD_ROLE_MENTION_ID", default=None
)

# Discord Connected
DISCORD_CONNECTED_GUILD_ID = env("DISCORD_CONNECTED_GUILD_ID", default=None)
DISCORD_CONNECTED_ROLE_ID = env("DISCORD_CONNECTED_ROLE_ID", default=None)

# Google Maps
GOOGLE_MAPS_API_KEY = env("GOOGLE_MAPS_API_KEY", default=None)

# https://app.platerecognizer.com/service/snapshot-cloud/
PLATERECOGNIZER_API_KEY = env("PLATERECOGNIZER_API_KEY", default=None)

NEW_LASER_VIOLATION_GUILD_ID = env("NEW_LASER_VIOLATION_GUILD_ID", default=None)
NEW_LASER_VIOLATION_CHANNEL_ID = env("NEW_LASER_VIOLATION_CHANNEL_ID", default=None)

# django-admin-csvexport
# https://github.com/thomst/django-admin-csvexport/issues/3
DATA_UPLOAD_MAX_NUMBER_FIELDS = None
CSV_EXPORT_FORMAT_FORM = True
CSV_EXPORT_DELIMITER = ","
CSV_EXPORT_ESCAPECHAR = "\\"
CSV_EXPORT_QUOTECHAR = '"'
CSV_EXPORT_DOUBLEQUOTE = True
CSV_EXPORT_LINETERMINATOR = r"\n"
CSV_EXPORT_QUOTING = "QUOTE_ALL"

MARKDOWNIFY = {
    "default": {
        "WHITELIST_TAGS": [
            "a",
            "abbr",
            "acronym",
            "b",
            "blockquote",
            "code",
            "em",
            "i",
            "li",
            "ol",
            "strong",
            "ul",
            "p",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
        ],
        "MARKDOWN_EXTENSIONS": [
            "extra",
            "nl2br",
        ],
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}
