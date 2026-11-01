#!/bin/sh
# Essai de SoluGation accessible depuis Internet, sans serveur ni nom de domaine : tunnel Cloudflare gratuit vers ce poste.
# Configuration de production (gunicorn, interface compilée, service de tâches), données à part (.env.essai, volumes
# « solugation-essai »). Le chiffrement s'arrête chez Cloudflare : DONNÉES FICTIVES UNIQUEMENT. L'adresse change à
# chaque démarrage du tunnel ; l'appli n'est joignable que tant que ce poste est allumé.
#
#   scripts/essai-cloudflare.sh demarrer   construit, démarre, affiche l'adresse publique
#   scripts/essai-cloudflare.sh adresse    réaffiche l'adresse
#   scripts/essai-cloudflare.sh arreter    arrête (les données restent)
#   scripts/essai-cloudflare.sh effacer    arrête et supprime toutes les données de l'essai
set -eu
cd "$(dirname "$0")/.."
FICHIER=.env.essai
export SOLUGATION_FICHIER_ENV="$FICHIER"
COMPOSE="docker compose -p solugation-essai -f docker-compose.prod.yml --env-file $FICHIER"

secret() { openssl rand -base64 64 | tr -d '/+=\n' | cut -c1-"$1"; }
adresse() { $COMPOSE logs tunnel 2>/dev/null | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1; }
# Remplace (ou ajoute) VARIABLE=valeur dans le fichier d'essai.
regler() {
  if grep -q "^$1=" "$FICHIER"; then sed -i.bak "s|^$1=.*|$1=$2|" "$FICHIER" && rm -f "$FICHIER.bak"; else echo "$1=$2" >> "$FICHIER"; fi
}

preparer() {
  [ -f "$FICHIER" ] && return
  umask 077
  cp .env.production.example "$FICHIER"
  regler DJANGO_SECRET_KEY "$(secret 50)"
  regler POSTGRES_PASSWORD "$(secret 24)"
  regler S3_SECRET_KEY "$(secret 24)"
  regler SOLUGATION_DOMAINE "en-attente.trycloudflare.com"
  regler EMAIL_HOST ""
  regler COMPOSE_PROFILES "stockage-local,tunnel-cloudflare"
  regler SOLUGATION_FICHIER_ENV "$FICHIER"  # lu par Compose : les commandes affichées fonctionnent telles quelles
  # HTTPS assuré par Cloudflare ; deux proxys (tunnel puis Caddy) devant le serveur ; rien d'ouvert sur le réseau local.
  regler SOLUGATION_TLS externe
  regler SOLUGATION_PROXYS_AMONT private_ranges
  regler SOLUGATION_NB_PROXYS 2
  regler SOLUGATION_ECOUTE 127.0.0.1
  regler SOLUGATION_PORT_HTTP 8090
  regler SOLUGATION_PORT_HTTPS 8493
  echo "Configuration d'essai créée : $FICHIER (secrets générés, jamais commité)."
}

case "${1:-demarrer}" in
  demarrer)
    preparer
    $COMPOSE up -d --build --wait
    printf "Ouverture du tunnel"
    for _ in $(seq 1 60); do
      [ -n "$(adresse)" ] && break
      printf "."; sleep 1
    done
    echo
    URL=$(adresse)
    [ -n "$URL" ] || { echo "Pas d'adresse Cloudflare : voir « $COMPOSE logs tunnel »." >&2; exit 1; }
    # Le serveur n'accepte que son nom de domaine : on lui donne celui du tunnel.
    regler SOLUGATION_DOMAINE "${URL#https://}"
    $COMPOSE up -d --wait backend taches >/dev/null 2>&1
    cat <<FIN

SoluGation est en ligne : $URL

Premier lancement : importer les référentiels et créer l'organisation et son administrateur :
  $COMPOSE exec backend python manage.py importer_referentiel libres
  $COMPOSE exec backend python manage.py creer_organisation --nom "Essai" --email vous@exemple.fr --admin-installation

Pas de serveur de mails dans l'essai : créez les comptes des collègues avec un mot de passe à leur transmettre,
  $COMPOSE exec backend python manage.py creer_utilisateur --organisation essai --email collegue@exemple.fr

Rappel : données fictives uniquement. Arrêt : scripts/essai-cloudflare.sh arreter
FIN
    ;;
  adresse) adresse ;;
  arreter) $COMPOSE stop ;;
  effacer) $COMPOSE down -v && rm -f "$FICHIER" && echo "Essai effacé." ;;
  *) echo "Usage : $0 demarrer|adresse|arreter|effacer" >&2; exit 1 ;;
esac
