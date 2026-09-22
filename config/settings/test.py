from .base import *  # noqa: F401, F403

DEBUG = False

# Test database: use SQLite for speed (no Docker dependency)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Faster password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable CORS in tests
CORS_ALLOW_ALL_ORIGINS = False

# Quiet logging during tests
LOGGING: dict = {}  # noqa: F811
