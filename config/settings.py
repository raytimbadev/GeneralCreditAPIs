"""Definições da API BCI (serviço standalone, rede interna).

Configuração por variáveis de ambiente — ver `deploy/env.example`.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "rest_framework.authtoken",
    "bci",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# A simulação não persiste nada — a base só guarda utilizadores e tokens.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", "/var/lib/bci-api/db.sqlite3"),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

LANGUAGE_CODE = "pt"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Africa/Maputo")
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Documentação em /api/bci/docs e /api/bci/openapi.yaml, sem autenticação.
# Pôr BCI_DOCS=0 para a esconder (passa a 404).
BCI_DOCS = os.environ.get("BCI_DOCS", "1") not in ("0", "false", "False")

# Agravamento fixo aplicado ao prémio (0.10 = 10 %).
BCI_AGRAVAMENTO = float(os.environ.get("BCI_AGRAVAMENTO", "0"))
