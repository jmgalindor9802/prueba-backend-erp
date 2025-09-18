#!/bin/bash
set -euo pipefail

python manage.py migrate --noinput

if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

if [ "${USE_GUNICORN:-1}" = "1" ]; then
  exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" --threads "${GUNICORN_THREADS:-1}"
else
  exec python manage.py runserver 0.0.0.0:8000
fi