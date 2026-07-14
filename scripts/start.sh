#!/bin/sh
set -e

cd /app/backend
python manage.py migrate --noinput

gunicorn --bind 127.0.0.1:8000 --workers 2 config.wsgi:application &

cd /app/frontend
exec npx next start -H 0.0.0.0 -p "${PORT:-3000}"
