#!/bin/sh
# Démarrage des conteneurs de production : serveur web (par défaut) ou service de tâches.
set -e

case "${1:-web}" in
  web)
    # Configuration dangereuse (secret d'exemple, aucun nom de domaine…) : arrêt immédiat, message explicite.
    python manage.py check --deploy --tag security --fail-level ERROR
    python manage.py migrate --noinput
    python manage.py initialiser_stockage
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" --timeout 120 --graceful-timeout 30 \
      --max-requests 1000 --max-requests-jitter 100 --access-logfile -
    ;;
  taches)
    exec python manage.py executer_taches
    ;;
  *)
    exec "$@"
    ;;
esac
