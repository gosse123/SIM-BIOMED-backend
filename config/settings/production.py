import os

from .base import *  # noqa: F401, F403
from .origins import allowed_hosts, cors_origins, csrf_origins

DEBUG = False

# Security: SECRET_KEY must be set in env
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Hôtes et origines réels : voir config.settings.origins (suffixe Render,
# origine du front indispensable pour éviter le 403 CSRF).
render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
frontend_origin = os.environ.get("FRONTEND_ORIGIN", "").strip()

ALLOWED_HOSTS = allowed_hosts(os.environ.get("ALLOWED_HOSTS", ""), render_host)  # noqa: F405

# CORS
CORS_ALLOWED_ORIGINS = cors_origins(  # noqa: F405
    os.environ.get("CORS_ALLOWED_ORIGINS", ""), frontend_origin
)

# CSRF
CSRF_TRUSTED_ORIGINS = csrf_origins(  # noqa: F405
    os.environ.get("CSRF_TRUSTED_ORIGINS", ""), render_host, frontend_origin
)

# WhiteNoise : sert les fichiers statiques (admin, collectstatic) sans Nginx
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

# HTTPS / HSTS (le TLS est terminé par le proxy de la plateforme)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() == "true"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Browser security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# Database
if not os.environ.get("DATABASE_URL", "").strip():  # noqa: F405
    DATABASES["default"]["HOST"] = os.environ.get("DB_HOST", "db")  # noqa: F405
    DATABASES["default"]["PORT"] = os.environ.get("DB_PORT", "5432")  # noqa: F405
DATABASES["default"]["CONN_MAX_AGE"] = 600  # noqa: F405

# Static files
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Logging: structured JSON for production
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": (
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"name":"%(name)s","message":"%(message)s"}'
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "WARNING"),
    },
}
