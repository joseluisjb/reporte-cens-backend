#!/bin/sh
set -e

python manage.py seed_usuarios

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120
