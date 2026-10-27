#!/bin/sh
# Sauvegarde complète de SoluGation en production : base PostgreSQL puis fichiers du stockage S3,
# dans sauvegardes/AAAA-MM-JJ_HHMMSS/, avec empreintes SHA-256. Rotation : SAUVEGARDE_JOURS (14 par défaut).
# À planifier chaque nuit sur l'hôte, par exemple :  30 2 * * * /opt/solugation/scripts/sauvegarder.sh
# Copiez ensuite le dossier hors du serveur (autre site), de préférence chiffré : voir docs/15-production.md.
set -eu
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.production"
NOM=$(date +%Y-%m-%d_%H%M%S)
DOSSIER="sauvegardes/$NOM"
umask 077
mkdir -p "$DOSSIER"

empreinte() { if command -v sha256sum >/dev/null; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }

# 1. La base d'abord : les fichiers étant immuables, tout fichier cité par la base sera dans la copie qui suit.
$COMPOSE exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$DOSSIER/base.dump"
# 2. Les fichiers, par l'application (fonctionne avec le stockage intégré comme avec un S3 externe).
$COMPOSE exec -T -u 0 backend python manage.py sauvegarder_stockage "/sauvegardes/$NOM/fichiers"
(cd "$DOSSIER" && empreinte base.dump fichiers/inventaire.json > SHA256SUMS)
chmod -R go-rwx "$DOSSIER"

find sauvegardes -mindepth 1 -maxdepth 1 -type d -mtime +"${SAUVEGARDE_JOURS:-14}" -exec rm -rf {} +
echo "Sauvegarde terminée : $DOSSIER ($(du -sh "$DOSSIER" | cut -f1))"
