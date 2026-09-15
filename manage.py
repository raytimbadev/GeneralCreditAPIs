#!/usr/bin/env python
"""Utilitário de linha de comandos do Django."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar o Django. Está instalado e o "
            "virtualenv activado?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
