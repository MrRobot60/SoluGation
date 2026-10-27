# Installation

Cette page décrit l'installation avec **Docker Compose**, telle que fournie dans le dépôt. Elle convient au développement, à l'évaluation et aux tests avec des collègues sur un réseau maîtrisé.

> **Production.** Le `docker-compose.yml` décrit ici lance les serveurs de développement (Django `runserver`, Vite) et un relais de mails de test : ne l'exposez pas sur Internet. Pour un serveur accessible par vos utilisateurs (HTTPS, sauvegardes, tâches planifiées), suivez [Déployer en production](15-production.md).

## 1. Prérequis

| Élément | Version | Remarque |
|---|---|---|
| Docker Engine + Docker Compose v2 | récents | Sous macOS : Docker Desktop, ou **Colima** (gratuit) |
| Git | — | pour récupérer le code |
| 4 Go de mémoire libre | — | PostgreSQL, stockage, serveur, interface |
| Ports locaux libres | 5173, 8000, 5432, 8333, 8025 | tous liés à `127.0.0.1` uniquement |

### macOS avec Colima

```bash
brew install colima docker docker-compose
colima start --cpu 4 --memory 6 --vm-type vz
```

Si `docker compose` n'est pas reconnu, déclarez le greffon : dans `~/.docker/config.json`, ajoutez `"cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]`.

### Linux

Installez Docker Engine et le greffon Compose depuis les dépôts officiels de Docker, puis ajoutez votre utilisateur au groupe `docker`.

## 2. Récupérer le code et préparer `.env`

```bash
git clone <adresse-du-dépôt> solugation
cd solugation
cp .env.example .env
```

Ouvrez `.env` et remplacez **toutes** les valeurs `a-remplacer`. Générer des secrets solides :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # POSTGRES_PASSWORD, S3_SECRET_KEY
```

- Reportez le mot de passe PostgreSQL **à deux endroits** : `POSTGRES_PASSWORD` et dans `DATABASE_URL`.
- `.env` contient des secrets : il est exclu de Git (`.gitignore`). Ne le partagez jamais.

Toutes les variables sont détaillées dans [la configuration](03-configuration.md).

## 3. Démarrer

```bash
docker compose up -d
docker compose ps          # tous les services doivent être « running » (healthy pour postgres et stockage)
```

| Service | Rôle | Adresse |
|---|---|---|
| `postgres` | Base de données PostgreSQL 17 | `127.0.0.1:5432` |
| `stockage` | Stockage de fichiers compatible S3 (SeaweedFS) | `127.0.0.1:8333` |
| `mail` | Mailpit : capture **tous** les mails, rien ne sort | <http://localhost:8025> |
| `backend` | API Django (migrations et bucket créés au démarrage) | <http://localhost:8000/api/sante/> |
| `frontend` | Interface (React) | <http://localhost:5173> |

Au premier démarrage, le serveur applique les migrations et crée le bucket de stockage (`initialiser_stockage`). Le premier `npm ci` de l'interface prend une à deux minutes : suivez-le avec `docker compose logs -f frontend`.

## 4. Importer les référentiels libres

```bash
docker compose exec backend python manage.py importer_referentiel libres
```

NIST CSF, OWASP ASVS et le guide d'hygiène ANSSI sont **téléchargés** depuis leur site officiel. Deux référentiels doivent être **déposés à la main** (les sites officiels ne proposent pas de lien stable) :

| Référentiel | Fichier(s) à placer dans | Source |
|---|---|---|
| II 901 | `data/sources/ii901/2015/cir_39217.pdf` | Légifrance, circulaire n° 39217 |
| RGS v2.0 | `data/sources/rgs/2.0/` : `RGS_v-2-00_Corps_du_texte.pdf`, `RGS_v-2-0_B1.pdf`, `RGS_v-2-0_B2.pdf`, `RGS_v-2-0_B3.pdf` | cyber.gouv.fr |

Relancez ensuite la commande : elle est **idempotente** (ce qui existe est mis à jour, rien n'est dupliqué). ISO 27001, norme payante, s'importe depuis votre copie licenciée : voir [les référentiels](08-referentiels.md).

## 5. Créer l'organisation et le premier administrateur

```bash
docker compose exec backend python manage.py creer_organisation \
  --nom "Mon organisation" --secteur public \
  --email moi@exemple.fr --prenom Prénom --nom-famille Nom \
  --admin-installation
```

Le mot de passe est **demandé de façon masquée** (12 caractères minimum, pas trop courant). `--admin-installation` fait aussi de ce compte l'administrateur de l'installation (configuration de l'IA, admin Django). Ajoutez d'autres comptes avec `creer_utilisateur` (voir [premiers pas](04-premiers-pas.md)).

Ouvrez <http://localhost:5173>, connectez-vous : la page d'accueil propose de **créer un projet**.

## 6. (Facultatif) Données de démonstration

```bash
docker compose exec backend python manage.py creer_demo
```

Crée l'organisation « Démo SoluGation » avec un projet « Portail usagers » déjà avancé. Réservé au développement (`DJANGO_DEBUG=True`) ; le compte utilisé est lu dans `DEV_ADMIN_EMAIL` / `DEV_ADMIN_PASSWORD` du `.env`.

## 7. Arrêter, relancer, mettre à jour

```bash
docker compose stop                 # arrêter (les données restent)
docker compose up -d                # relancer
git pull && docker compose build backend && docker compose up -d   # mettre à jour
```

> **Après avoir modifié `.env`**, utilisez `docker compose up -d` (qui recrée les conteneurs) et **non** `docker compose restart` : `restart` ne relit pas le fichier.

Les migrations s'appliquent automatiquement au démarrage du serveur. Si une dépendance Python change (`backend/requirements.txt`), reconstruisez l'image : `docker compose build backend`.

## 8. Sauvegarder et restaurer

En développement, les données vivent dans deux volumes Docker : `solugation_postgres_data` (base) et `solugation_stockage_data` (fichiers). Pour une copie ponctuelle de la base :

```bash
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > sauvegarde-$(date +%F).dump
```

En production, les scripts `scripts/sauvegarder.sh` et `scripts/restaurer.sh` sauvegardent base et fichiers avec empreintes : voir [production](15-production.md#6-sauvegardes).

Sauvegardez aussi `.env` (dans un coffre) : sans `DJANGO_SECRET_KEY`, la clé d'API de l'IA enregistrée à l'écran ne peut plus être déchiffrée.

## 9. Tout effacer (repartir de zéro)

```bash
docker compose down -v      # supprime conteneurs ET volumes : base et fichiers perdus
```
