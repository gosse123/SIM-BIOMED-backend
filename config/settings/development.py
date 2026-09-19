from .base import *  # noqa: F401, F403
import os

DEBUG = True

ALLOWED_HOSTS = ["*"]

DATABASES["default"]["HOST"] = os.environ.get("DB_HOST", "localhost")  # noqa: F405
DATABASES["default"]["PORT"] = os.environ.get("DB_PORT", "5432")  # noqa: F405

CORS_ALLOW_ALL_ORIGINS = True
