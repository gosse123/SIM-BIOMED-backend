import os

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Base externe (DATABASE_URL) : ne pas écraser HOST/PORT — c'est dj_database_url
# qui les a déjà posés (pooler Supabase, sslmode=require).
if not os.environ.get("DATABASE_URL", "").strip():  # noqa: F405
    DATABASES["default"]["HOST"] = os.environ.get("DB_HOST", "localhost")  # noqa: F405
    DATABASES["default"]["PORT"] = os.environ.get("DB_PORT", "5432")  # noqa: F405

CORS_ALLOW_ALL_ORIGINS = True
