import os

# Se define antes del import: settings.py exige la clave cuando DEBUG es False.
if not os.environ.get("DJANGO_SECRET_KEY"):
    os.environ["DJANGO_SECRET_KEY"] = "clave-solo-para-pruebas"

from config.settings import *  # noqa: E402

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
