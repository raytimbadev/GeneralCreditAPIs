from settings_test import *  # noqa: F401,F403

ALLOWED_HOSTS = ["*"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "db_dev.sqlite3"}}
