# Configuration

Toute la configuration passe par le fichier **`.env`** à la racine (copié depuis `.env.example`). Les variables déjà présentes dans l'environnement du conteneur priment sur le fichier. Après une modification : `docker compose up -d` (et non `restart`).

## Django

| Variable | Exemple | Rôle |
|---|---|---|
| `DJANGO_SECRET_KEY` | 50 caractères aléatoires | Signature des sessions et jetons. Sert aussi à dériver la clé de chiffrement de la clé d'API de l'IA si `IA_CLE_CHIFFREMENT` est vide. **Ne la changez pas sans raison** : sessions déconnectées et clé d'IA à ressaisir. |
| `DJANGO_DEBUG` | `True` en dev, `False` sinon | En `False` : HTTPS imposé, cookies sécurisés, HSTS. `creer_demo` refuse de tourner. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,backend` | Noms d'hôte acceptés. Garder `backend` (l'interface y accède dans Docker). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `http://localhost:5173` | Origine(s) de l'interface, schéma compris. |
| `FRONTEND_URL` | `http://localhost:5173` | Adresse publique de l'interface, utilisée dans les liens des mails et des invitations. |

## Sécurité des comptes

| Variable | Exemple | Rôle |
|---|---|---|
| `DOUBLE_AUTH_POLITIQUE` | `facultative` (défaut), `desactivee`, `administrateurs`, `tous` | Double authentification par application (TOTP). L'écran **Administration** (administrateur de l'installation) prime sur cette valeur. |
| `SOLUGATION_CLE_CHIFFREMENT` | clé Fernet | Chiffre les secrets de double authentification en base. Vide : dérivée de `DJANGO_SECRET_KEY` (la changer oblige alors à réinitialiser la double authentification de chaque compte). Générer : `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

Les limites de tentatives (connexion, codes, demandes de lien) sont comptées dans une table de cache en base (`solugation_cache`, créée au démarrage par `createcachetable`) : elles valent pour tous les processus du serveur.

## Base de données

| Variable | Exemple | Rôle |
|---|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `solugation` | Création de la base par le conteneur PostgreSQL. |
| `DATABASE_URL` | `postgres://solugation:MOTDEPASSE@postgres:5432/solugation` | Connexion de l'application. Même mot de passe que ci-dessus. |

## Stockage des fichiers (S3)

Les documents, preuves, rapports de scan et PDF sont rangés dans un stockage **compatible S3** (SeaweedFS en local, ou tout service S3 : Scaleway, OVHcloud, MinIO, Garage…), sous un préfixe propre à chaque organisation, avec un nom de fichier régénéré.

| Variable | Exemple | Rôle |
|---|---|---|
| `S3_ENDPOINT_URL` | `http://stockage:8333` | Adresse du service S3. |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | — | Identifiants (8 caractères minimum pour SeaweedFS). |
| `S3_BUCKET` | `solugation` | Bucket, créé au démarrage s'il n'existe pas (versioning activé). |
| `S3_REGION` | `fr-par` | Région (ignorée par SeaweedFS). |
| `S3_USE_SSL` | `False` en local, `True` sinon | HTTPS vers le stockage. |
| `S3_SSE` | vide, ou `AES256` | Chiffrement côté serveur du stockage (à activer chez un hébergeur). |
| `UPLOAD_MAX_MO` | `50` | Taille maximale d'un fichier déposé. |
| `SOLUGATION_DATA_DIR` | `/data` (fixé par Docker) | Dossier des sources de référentiels (`sources/`) et des copies licenciées (`private/`). |

## Mails

En développement, Docker Compose force l'envoi vers **Mailpit** (rien ne sort, consultation sur <http://localhost:8025>). Sans `EMAIL_HOST`, les mails sont affichés dans les journaux du serveur.

| Variable | Exemple | Rôle |
|---|---|---|
| `DEFAULT_FROM_EMAIL` | `SoluGation <notifications@exemple.fr>` | Expéditeur, aussi organisateur des invitations d'agenda. |
| `EMAIL_HOST`, `EMAIL_PORT` | `smtp.exemple.fr`, `587` | Relais SMTP. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | — | Authentification au relais. |
| `EMAIL_USE_TLS` | `True` | STARTTLS (obligatoire hors développement). |

## Intelligence artificielle (facultative)

Sans configuration, **aucune IA** : les fonctions IA sont masquées et tout fonctionne. Le plus simple est de configurer le fournisseur **depuis l'écran Administration** (il prime sur ce fichier). Détails, choix du fournisseur et confidentialité : [Intelligence artificielle](07-ia.md).

| Variable | Exemple | Rôle |
|---|---|---|
| `IA_FOURNISSEUR` | `aucun` (défaut), `compatible`, `scaleway`, `mistral`, `factice` | `compatible` = toute API compatible OpenAI. `factice` = hors ligne, réservé au développement et aux tests. |
| `IA_NOM` | `IA interne` | Nom affiché et journalisé. |
| `IA_URL` | `https://api.fournisseur.eu/v1` | Adresse de l'API (`/chat/completions` y est ajouté). |
| `IA_MODELE` | `mistral-small-latest` | Identifiant du modèle. |
| `IA_CLE` | — | Clé d'API (facultative pour un modèle local). |
| `IA_ZDR_CONFIRME` | `False` | `True` = l'administrateur accepte la responsabilité des conditions du fournisseur. Sans cela, rien n'est envoyé. |
| `IA_CLE_CHIFFREMENT` | clé Fernet | Chiffre la clé d'API saisie à l'écran. Vide : dérivée de `DJANGO_SECRET_KEY`. Générer : `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `IA_AUTORISER_RESEAU_LOCAL` | `False` | `True` pour une IA sur le réseau local (Ollama, vLLM) : lève la protection SSRF qui refuse les adresses internes et le HTTP. |
| `MISTRAL_API_KEY`, `MISTRAL_MODELE`, `MISTRAL_URL`, `MISTRAL_ZDR_CONFIRME` | — | Raccourci `IA_FOURNISSEUR=mistral`. |
| `IA_EXECUTION` | `fil` (dev), `taches` (production, fixé par `docker-compose.prod.yml`) | Où s'exécutent les analyses : fil d'arrière-plan du serveur web, ou service `taches` dédié. |
| `IA_SYNCHRONE` | `False` | Exécute les analyses dans la requête (tests uniquement). |

## Production

Fichier `.env.production` (modèle : `.env.production.example`), lu par `docker-compose.prod.yml`. Voir [Déployer en production](15-production.md).

| Variable | Exemple | Rôle |
|---|---|---|
| `SOLUGATION_DOMAINE` | `solugation.exemple.fr` | Nom de domaine public. Certificat HTTPS automatique ; `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` et `FRONTEND_URL` s'en déduisent s'ils sont vides. |
| `POSTGRES_PASSWORD` | — | Saisi une seule fois : `DATABASE_URL` est construite par Compose. |
| `COMPOSE_PROFILES` | `stockage-local` | Lance le stockage S3 intégré. Vide pour un S3 externe. |
| `SOLUGATION_ENVOI_MAX_MO` | `60` | Taille maximale d'une requête acceptée par le proxy (un peu plus que `UPLOAD_MAX_MO`). |
| `GUNICORN_WORKERS` | `3` | Processus du serveur web. |
| `SOLUGATION_PORT_HTTP`, `SOLUGATION_PORT_HTTPS` | `80`, `443` | Ports publiés (à changer seulement pour un essai local). |
| `SOLUGATION_TLS` | `auto` (défaut), `certificat`, `interne`, `externe` | Mode HTTPS : voir [modes HTTPS](15-production.md#modes-https). |
| `SOLUGATION_PROXYS_AMONT` | `10.0.4.12/32` ou `private_ranges` | Mode `externe` : adresses du proxy amont dont Caddy accepte les en-têtes `X-Forwarded-*`. Par défaut : aucun. |
| `SOLUGATION_NB_PROXYS` | `1` (Caddy seul), `2` (proxy amont + Caddy) | Nombre de proxys devant le serveur, pour retrouver l'adresse réelle du client dans `X-Forwarded-For`. |
| `SOLUGATION_ECOUTE` | `0.0.0.0` (défaut), `127.0.0.1`, une adresse de l'hôte | Interface sur laquelle le proxy écoute. |
| `SOLUGATION_URL_CODE_SOURCE` | `https://github.com/MrRobot60/SoluGation` (défaut) | Lien « Code source » affiché aux utilisateurs (page de connexion, Aide). **Obligatoire si vous proposez en ligne une version modifiée** (AGPL-3.0, art. 13) : indiquez le dépôt de votre version. |
| `SOLUGATION_FICHIER_ENV` | `.env.production` (défaut) | Fichier de configuration lu par les services (l'essai Cloudflare utilise `.env.essai`). |
| `SOLUGATION_PROXY_DE_CONFIANCE` | `True` (fixé par Compose) | L'adresse du client est lue dans `X-Forwarded-For`, posé par Caddy. **Jamais** sans proxy devant : l'en-tête serait falsifiable. |
| `SAUVEGARDE_JOURS` | `14` | Variable du shell pour `scripts/sauvegarder.sh` : durée de conservation des sauvegardes locales. |

Fixés par `docker-compose.prod.yml` : `DJANGO_DEBUG=False`, `IA_EXECUTION=taches`, `SOLUGATION_PROXY_DE_CONFIANCE=True`, `DATABASE_URL`, `SOLUGATION_DATA_DIR=/data`.

## Démonstration (développement)

| Variable | Rôle |
|---|---|
| `DEV_ADMIN_EMAIL`, `DEV_ADMIN_PASSWORD` | Compte administrateur créé par `manage.py creer_demo`. |

## Valeurs imposées par Docker Compose

Le service `backend` fixe `SOLUGATION_DATA_DIR=/data`, `EMAIL_HOST=mail`, `EMAIL_PORT=1025`, `EMAIL_USE_TLS=False` (Mailpit). Le service `frontend` fixe `SOLUGATION_BACKEND=http://backend:8000` (relais de l'API par Vite) et `SOLUGATION_SCRUTATION=1` (détection des modifications de fichiers dans Docker).
