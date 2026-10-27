#!/bin/sh
# Restaure une sauvegarde de scripts/sauvegarder.sh : REMPLACE la base actuelle, puis remet les fichiers.
# Usage : scripts/restaurer.sh sauvegardes/AAAA-MM-JJ_HHMMSS [--oui]
set -eu
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.production"
NOM=$(basename "${1:?Usage : scripts/restaurer.sh sauvegardes/AAAA-MM-JJ_HHMMSS [--oui]}")
DOSSIER="sauvegardes/$NOM"
[ -f "$DOSSIER/base.dump" ] && [ -f "$DOSSIER/fichiers/inventaire.json" ] || { echo "Sauvegarde introuvable : $DOSSIER" >&2; exit 1; }

verifier() { if command -v sha256sum >/dev/null; then sha256sum -c --quiet SHA256SUMS; else shasum -a 256 -c --quiet SHA256SUMS; fi; }
(cd "$DOSSIER" && verifier) || { echo "Empreintes invalides : sauvegarde altérée, restauration annulée." >&2; exit 1; }

if [ "${2:-}" != "--oui" ]; then
  printf "La base actuelle sera REMPLACÉE par la sauvegarde %s. Taper « restaurer » pour continuer : " "$NOM"
  read -r reponse
  [ "$reponse" = "restaurer" ] || { echo "Annulé."; exit 1; }
fi

$COMPOSE stop proxy taches backend
$COMPOSE up -d --wait postgres
$COMPOSE exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
$COMPOSE exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' < "$DOSSIER/base.dump"
# Fichiers : les empreintes sont revérifiées par l'application avant tout envoi.
$COMPOSE run --rm -u 0 backend python manage.py restaurer_stockage "/sauvegardes/$NOM/fichiers"
$COMPOSE up -d
echo "Restauration terminée depuis $DOSSIER. Vérifiez l'intégrité du journal d'audit (Administration)."
