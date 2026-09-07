"""Development settings.

Reads from a local `.env` file if present. Falls back to SQLite when
`DATABASE_URL` is not set, so a new contributor without Docker/Postgres
can still run the dev server and the test suite.
"""

import environ

from .base import *  # noqa: F403
from .base import BASE_DIR, env

environ.Env.read_env(str(BASE_DIR / ".env"))

DEBUG = env.bool("DEBUG", default=True)

SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-secret-key")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
