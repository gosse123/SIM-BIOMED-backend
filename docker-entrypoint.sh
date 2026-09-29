#!/bin/sh
# Point d'entrée de l'image de production.
# Migrations et collectstatic sont exécutés au démarrage puis le CMD est lancé.
# Désactivables par service : RUN_MIGRATIONS=false / RUN_COLLECTSTATIC=false
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Applying database migrations..."
  attempts=0
  until python manage.py migrate --noinput; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 5 ]; then
      echo "Migrations aborted after $attempts attempts." >&2
      exit 1
    fi
    echo "Database not ready, retrying in 3s ($attempts/5)..."
    sleep 3
  done
fi

if [ "${RUN_COLLECTSTATIC:-true}" = "true" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

exec "$@"
