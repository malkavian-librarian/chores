"""Production settings.

`DEBUG` is hardcoded to `False` here — never derived from an
environment variable, so a misconfigured env var can't accidentally
run production with debugging enabled.
"""

from .base import *  # noqa: F403
from .base import MIDDLEWARE, env

DEBUG = False

SECRET_KEY = env("SECRET_KEY")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# WhiteNoise serves collected static files in production; dev relies on
# Django's own static file handling instead (see dev.py).
MIDDLEWARE = [*MIDDLEWARE[:1], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
