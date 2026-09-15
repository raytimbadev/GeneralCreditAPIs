SECRET_KEY = "test"
DEBUG = True
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes",
    "rest_framework", "rest_framework.authtoken", "bci",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ROOT_URLCONF = "urls_test"
USE_TZ = True
BCI_AGRAVAMENTO = 0
