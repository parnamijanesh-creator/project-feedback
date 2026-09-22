"""Local development settings for Weekly Team Feedback Tool."""
from .base import *  # noqa: F403
from .base import BASE_DIR, env

DEBUG = env.bool("DEBUG", default=True)

SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-dev-key-change-in-production-weekly-feedback-local",
)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost", "0.0.0.0", "*"])

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
