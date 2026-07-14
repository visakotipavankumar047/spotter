#!/bin/sh
set -e

cd /app/backend
python manage.py migrate --noinput

gunicorn --bind 127.0.0.1:8000 --workers 2 config.wsgi:application &

cd /app/frontend
export PORT="${PORT:-3000}"
export HOSTNAME="${HOSTNAME:-0.0.0.0}"
exec /usr/local/bin/node server.js
