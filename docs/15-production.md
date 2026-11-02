# Déployer en production

Cette page installe SoluGation sur un serveur accessible par vos utilisateurs, en **HTTPS**, avec sauvegardes. Elle ne dépend d'aucun hébergeur : une machine Linux avec Docker suffit (VM chez un hébergeur, serveur de votre SI).

## Ce qui change par rapport au développement

| Élément | Développement (`docker-compose.yml`) | Production (`docker-compose.prod.yml`) |
|---|---|---|
| Serveur Django | `runserver`, `DEBUG=True` | **gunicorn** (plusieurs processus), `DEBUG=False` |
| Interface | Serveur Vite (rechargement à chaud) | Interface **compilée**, servie par **Caddy** |
| Accès | `http://localhost`, ports multiples | **HTTPS uniquement** (certificat Let's Encrypt automatique), ports 80 et 443 seulement |
| Base, stockage, serveur | Ports ouverts sur `127.0.0.1` | **Aucun port exposé** : réseau Docker interne |
| Analyses IA | Fil d'arrière-plan du serveur | Service **`taches`** dédié : une analyse survit au redémarrage du serveur web |
| Rappels (réunions, revues, dérogations) | Lancés à la main | Planifiés par le service `taches` : **pas de cron à installer** |
| Mails | Mailpit (rien ne sort) | Votre relais SMTP |
| Démarrage | Toujours | **Refusé** si une valeur d'exemple (`a-remplacer`) ou un réglage dangereux subsiste |
| Sauvegardes | — | `scripts/sauvegarder.sh` / `scripts/restaurer.sh` |

## Architecture

| Service | Image | Rôle | Exposé |
|---|---|---|---|
| `proxy` | `solugation-interface:prod` (Caddy + interface compilée) | HTTPS, en-têtes de sécurité, interface, relais de `/api`, `/admin`, `/static` | **80, 443** |
| `backend` | `solugation-backend:prod` | API Django (gunicorn), migrations au démarrage | non |
| `taches` | `solugation-backend:prod` | Analyses IA en attente, rappels planifiés | non |
| `postgres` | `postgres:17-alpine` | Base de données | non |
| `stockage` | `chrislusf/seaweedfs` | Stockage S3 intégré (facultatif : remplaçable par un S3 externe) | non |

## 1. Prérequis

| Élément | Détail |
|---|---|
| Serveur | Linux 64 bits, 2 vCPU, 4 Go de RAM, 20 Go de disque minimum (plus selon le volume de documents) |
| Logiciels | Docker Engine et le greffon Compose v2 (dépôts officiels de Docker) ; Git |
| Nom de domaine | Un enregistrement DNS `A` (et `AAAA` en IPv6) qui pointe vers le serveur, par ex. `solugation.exemple.fr` |
| Réseau | Ports **80 et 443** ouverts depuis Internet (ou depuis le réseau de vos utilisateurs) ; le port 80 sert à obtenir le certificat |
| Mails | Un relais SMTP (celui de votre organisation ou d'un prestataire) |
| Disque | **Chiffrement du disque** recommandé (données au repos), surtout avec le stockage intégré |

> **Serveur interne d'entreprise, sans accès depuis Internet** : tout fonctionne, y compris la double authentification. Voir [Installation interne](#installation-interne-en-entreprise) (certificat de l'organisation, installation sans Internet).
>
> **Juste essayer, sans serveur ni nom de domaine** : voir [Essai rapide avec un tunnel Cloudflare](#essai-rapide-avec-un-tunnel-cloudflare).

## 2. Récupérer le code et configurer

```bash
sudo mkdir -p /opt/solugation && sudo chown "$USER" /opt/solugation
git clone https://github.com/MrRobot60/SoluGation.git /opt/solugation
cd /opt/solugation
cp .env.production.example .env.production
chmod 600 .env.production
```

Générez les secrets (une valeur différente pour chacun) :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # POSTGRES_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # S3_SECRET_KEY
```

Puis éditez `.env.production` :

| Variable | À renseigner |
|---|---|
| `SOLUGATION_DOMAINE` | Le nom de domaine, sans `https://` (ex. `solugation.exemple.fr`). Il suffit : noms d'hôte autorisés, origine de confiance et liens des mails s'en déduisent. |
| `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `S3_SECRET_KEY` | Les secrets générés. Le mot de passe PostgreSQL n'est saisi **qu'une fois** (l'adresse de connexion est construite par Compose). |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Votre relais SMTP. |
| `GUNICORN_WORKERS` | Processus du serveur web : `2 × cœurs + 1` est un bon départ. |

Toutes les variables : [configuration](03-configuration.md#production).

**Conservez une copie de `.env.production` dans un coffre-fort** (gestionnaire de secrets) : sans `DJANGO_SECRET_KEY`, la clé d'API de l'IA enregistrée à l'écran ne se déchiffre plus.

## 3. Démarrer

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build --wait
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

Le premier démarrage construit les images (quelques minutes), applique les migrations, crée le bucket, puis Caddy obtient le certificat. Tous les services doivent être `running` (`healthy` pour `backend`, `postgres`, `stockage`).

Pour ne pas retaper les options, créez un alias :

```bash
echo 'alias sg="docker compose -f /opt/solugation/docker-compose.prod.yml --env-file /opt/solugation/.env.production"' >> ~/.bashrc
source ~/.bashrc
sg ps
```

La suite de cette page utilise `sg`.

### Si le serveur ne démarre pas

```bash
sg logs backend | grep -A3 -E "ERRORS|solugation.E"
```

| Message | Correction |
|---|---|
| `solugation.E001 … a encore sa valeur d'exemple` | Remplacer la valeur `a-remplacer` dans `.env.production` |
| `solugation.E002 DJANGO_SECRET_KEY est trop courte` | Générer une clé de 50 caractères |
| `solugation.E003 Aucun nom d'hôte autorisé` | Renseigner `SOLUGATION_DOMAINE` |
| `SOLUGATION_DOMAINE manquant` (au lancement de Compose) | Lancer avec `--env-file .env.production` |

Les **avertissements** (`solugation.W…`) ne bloquent pas mais sont à traiter : pas de SMTP (`W002`), stockage non chiffré (`W003`).

## 4. Initialiser

```bash
sg exec backend python manage.py importer_referentiel libres
sg exec backend python manage.py creer_organisation --nom "Mon organisation" --secteur public \
  --email moi@exemple.fr --prenom Prénom --nom-famille Nom --admin-installation
```

Les PDF à déposer à la main (II 901, RGS) vont dans `/opt/solugation/data/sources/…` (voir [référentiels](08-referentiels.md)).

Ouvrez `https://solugation.exemple.fr` et connectez-vous. Les nouveaux comptes se voient proposer la [visite guidée](06-guide-utilisateur.md#aide-et-visite-guidée).

## 5. Vérifier

| Contrôle | Commande ou action | Attendu |
|---|---|---|
| HTTPS | `curl -sI https://solugation.exemple.fr` | `HTTP/2 200`, en-têtes `strict-transport-security` et `content-security-policy` |
| Redirection | `curl -sI http://solugation.exemple.fr` | `308` vers `https://` |
| API | `curl -s https://solugation.exemple.fr/api/sante/` | `{"statut": "ok", …}` |
| Ports | `sudo ss -tlnp` | Seuls 80 et 443 (et SSH) écoutent publiquement |
| Mails | Ajouter un acteur à un projet | Mail reçu |
| Tâches | `sg logs taches` | `Service de tâches démarré.` puis les rappels |
| Journal | Administration → Vérifier l'intégrité | « Intègre » |

## 6. Sauvegardes

### Sauvegarder

```bash
/opt/solugation/scripts/sauvegarder.sh
```

Crée `sauvegardes/AAAA-MM-JJ_HHMMSS/` :

| Fichier | Contenu |
|---|---|
| `base.dump` | Base PostgreSQL complète (format `pg_dump` compressé) |
| `fichiers/` | Tous les fichiers du stockage S3 (documents, preuves, rapports PDF) et `inventaire.json` (empreinte SHA-256 de chacun) |
| `SHA256SUMS` | Empreintes de la base et de l'inventaire |

La base est sauvegardée **avant** les fichiers : les fichiers étant immuables, tout fichier cité par la base est dans la copie. Les sauvegardes de plus de 14 jours sont supprimées (`SAUVEGARDE_JOURS=30 scripts/sauvegarder.sh` pour en garder 30). Les dossiers ne sont lisibles que par leur propriétaire.

Planifiez-la chaque nuit (crontab de l'utilisateur qui gère Docker : `crontab -e`) :

```cron
30 2 * * * /opt/solugation/scripts/sauvegarder.sh >> /var/log/solugation-sauvegarde.log 2>&1
```

### Mettre les sauvegardes à l'abri

Une sauvegarde sur le même serveur ne protège ni d'une panne de disque, ni d'un rançongiciel. Copiez chaque nuit `sauvegardes/` **hors du serveur**, **chiffrée** : elle contient toutes les données des homologations.

```bash
# Exemple avec restic (dépôt chiffré : S3 d'un autre hébergeur, serveur SFTP…)
restic -r sftp:sauvegarde@autre-serveur:/solugation backup /opt/solugation/sauvegardes
```

Conservez aussi `.env.production` (coffre-fort) et le volume `caddy_data` (certificats ; recréés automatiquement sinon).

### Restaurer

```bash
/opt/solugation/scripts/restaurer.sh sauvegardes/2026-10-27_020000
```

Le script vérifie les empreintes, demande de taper `restaurer`, arrête le serveur, **remplace la base**, remet les fichiers (empreintes revérifiées avant tout envoi), puis redémarre. Ensuite, **Administration → Vérifier l'intégrité** du journal d'audit.

> **Testez une restauration** au moins une fois par trimestre, sur un serveur de test : une sauvegarde jamais restaurée n'est pas une sauvegarde.

Les fichiers déposés **après** la sauvegarde restent dans le stockage (non référencés par la base restaurée) : ils ne gênent pas le fonctionnement.

## 7. Mettre à jour

```bash
cd /opt/solugation
scripts/sauvegarder.sh                    # toujours avant une mise à jour
git pull
sg up -d --build --wait                   # reconstruit les images, applique les migrations
sg ps
```

En cas de problème : `git checkout <version précédente>`, `sg up -d --build`, et si une migration a modifié la base, restaurez la sauvegarde faite juste avant.

## 8. Exploitation courante

| Besoin | Commande |
|---|---|
| État des services | `sg ps` |
| Journaux | `sg logs -f backend` (ou `proxy`, `taches`, `postgres`) ; conservés 5 × 10 Mo par service |
| Redémarrer | `sg restart backend` ; après une modification de `.env.production` : `sg up -d` |
| Commande d'administration | `sg exec backend python manage.py <commande>` (voir [commandes](11-commandes.md)) |
| Ajouter un compte | `sg exec backend python manage.py creer_utilisateur --organisation <slug> --email …` |
| Arrêter | `sg stop` (les données restent) |

## Variantes

### Stockage S3 externe

Au lieu du stockage intégré, un Object Storage d'hébergeur (Scaleway, OVHcloud, Outscale…), redondant et chiffré :

```dotenv
COMPOSE_PROFILES=
S3_ENDPOINT_URL=https://s3.fr-par.scw.cloud
S3_ACCESS_KEY=<clé de l'hébergeur>
S3_SECRET_KEY=<secret de l'hébergeur>
S3_BUCKET=solugation-mon-organisation
S3_REGION=fr-par
S3_USE_SSL=True
S3_SSE=AES256
```

Le service `stockage` n'est alors plus lancé. Le bucket est créé au démarrage (versioning activé), sinon créez-le dans la console de l'hébergeur, **privé**. Les sauvegardes fonctionnent à l'identique.

### Modes HTTPS

Choisis par `SOLUGATION_TLS` dans `.env.production`, sans modifier aucun fichier :

| `SOLUGATION_TLS` | Pour qui | Ce qu'il faut |
|---|---|---|
| `auto` (défaut) | Serveur joignable depuis Internet | DNS vers le serveur, ports 80 et 443 ouverts : certificat Let's Encrypt automatique |
| `certificat` | Réseau interne d'entreprise | Le certificat de votre organisation dans `deploiement/certificats/` : `solugation.crt` (certificat et chaîne, PEM) et `solugation.key` (clé privée). Ces fichiers ne sont jamais commités. |
| `interne` | Laboratoire, réseau fermé sans PKI | Rien : Caddy crée sa propre autorité. Les navigateurs avertissent, sauf à installer sa racine sur les postes (volume `caddy_data`, `pki/authorities/local/root.crt`). |
| `externe` | HTTPS assuré en amont : répartiteur de charge, pare-feu applicatif (WAF), tunnel | Voir ci-dessous |

### Derrière un répartiteur de charge ou un pare-feu applicatif

Le proxy de l'organisation termine le HTTPS et transmet en HTTP à Caddy :

```dotenv
SOLUGATION_TLS=externe
SOLUGATION_PROXYS_AMONT=10.0.4.12/32   # adresse(s) du proxy amont, séparées par des espaces ; ou private_ranges
SOLUGATION_NB_PROXYS=2                  # proxy amont + Caddy
SOLUGATION_ECOUTE=10.0.4.20             # n'écouter que sur l'interface vue par le proxy amont
```

Le proxy amont doit envoyer `X-Forwarded-Proto: https` et ajouter l'adresse du client à `X-Forwarded-For` (comportement par défaut de HAProxy, nginx, F5, des répartiteurs cloud). **Vérifiez ensuite le journal d'audit** : l'adresse d'une connexion doit être celle du poste, pas celle du proxy. Une adresse de proxy amont mal renseignée a deux effets visibles : boucle de redirection vers HTTPS, ou adresse du proxy au journal.

### Installation interne en entreprise

SoluGation ne dépend d'**aucun service extérieur** pour fonctionner :

| Fonction | En réseau interne |
|---|---|
| Connexion, double authentification | Entièrement locale : codes calculés par le serveur, QR code généré par le serveur, applications de téléphone (Aegis, FreeOTP, Google ou Microsoft Authenticator…) qui fonctionnent **hors ligne**. Seule exigence : l'**heure du serveur synchronisée** (NTP interne) ; ±30 s sont tolérées. |
| Polices, scripts, interface | Servis par l'installation (aucun appel à un CDN) |
| Mails | Relais SMTP interne (`EMAIL_HOST`) ; sans relais, tout fonctionne sauf les mails (créer alors les comptes avec `creer_utilisateur`) |
| Stockage | Stockage intégré, ou S3 interne (MinIO, Ceph, NetApp StorageGRID…) |
| Certificat | `SOLUGATION_TLS=certificat` avec celui de votre PKI |
| IA | Facultative ; un modèle interne (Ollama, vLLM) avec `IA_AUTORISER_RESEAU_LOCAL=True` |
| Référentiels | NIST, OWASP et ANSSI se téléchargent depuis leur site : sans Internet, déposez les fichiers et passez `--fichier` (voir [référentiels](08-referentiels.md)) |

**Serveur sans accès à Internet** : construisez les images sur un poste connecté, puis transférez-les :

```bash
# Poste connecté
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker save solugation-backend:prod solugation-interface:prod postgres:17-alpine chrislusf/seaweedfs:4.48 | gzip > solugation-images.tar.gz
# Serveur interne (avec le dépôt et .env.production)
gunzip -c solugation-images.tar.gz | docker load
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --wait
```

Ou poussez ces images dans le registre interne de l'entreprise (Harbor, Nexus, GitLab…).

### Essai rapide avec un tunnel Cloudflare

Pour faire essayer SoluGation à quelques personnes **sans serveur ni nom de domaine** : la configuration de production tourne sur votre poste, et un tunnel Cloudflare gratuit (sans compte) lui donne une adresse publique en HTTPS.

```bash
scripts/essai-cloudflare.sh demarrer
```

Le script crée `.env.essai` (secrets générés, jamais commité), construit et démarre la pile, ouvre le tunnel et affiche l'adresse (`https://…trycloudflare.com`) ainsi que les commandes pour importer les référentiels et créer l'organisation. Les données de l'essai sont à part (projet Docker `solugation-essai`) : elles ne touchent ni au développement ni à une vraie installation.

| Commande | Effet |
|---|---|
| `scripts/essai-cloudflare.sh adresse` | Réaffiche l'adresse publique |
| `scripts/essai-cloudflare.sh arreter` | Arrête (les données restent) |
| `scripts/essai-cloudflare.sh effacer` | Supprime toutes les données de l'essai |

À savoir :

- **Données fictives uniquement** : le chiffrement s'arrête chez Cloudflare, qui voit passer les échanges.
- L'adresse change à **chaque démarrage** du tunnel (relancez `demarrer`, qui met la configuration à jour) ; l'appli n'est joignable que tant que votre poste est allumé.
- Pas de serveur de mails : créez les comptes des collègues avec `creer_utilisateur` et transmettez-leur le mot de passe par un autre canal.
- Rien n'est ouvert sur votre réseau local : le proxy n'écoute que sur `127.0.0.1`.

### Essai local de la configuration de production

Pour tester la configuration sur un poste avant de la déployer :

```dotenv
SOLUGATION_DOMAINE=localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost:8443
FRONTEND_URL=https://localhost:8443
SOLUGATION_PORT_HTTP=8080
SOLUGATION_PORT_HTTPS=8443
```

Caddy émet alors un certificat de sa propre autorité (le navigateur affiche un avertissement) : ouvrez `https://localhost:8443`.

## Sécurité de l'installation

| Mesure | Fournie par SoluGation | À votre charge |
|---|---|---|
| HTTPS, HSTS, redirection | Caddy + Django | Ouvrir 80/443 seulement |
| En-têtes (CSP stricte, anti-iframe, nosniff, Permissions-Policy) | Caddy | — |
| Services internes non exposés | Compose | Pare-feu de l'hôte (`ufw`, groupe de sécurité) |
| Secrets hors du dépôt, démarrage refusé sur valeur d'exemple | Oui | Coffre-fort pour `.env.production` |
| Conteneurs sans privilèges (utilisateur dédié) | Serveur et tâches | — |
| Adresse IP réelle au journal d'audit | Oui (via Caddy) | — |
| Chiffrement au repos | `S3_SSE` avec un S3 externe | Chiffrement du disque du serveur |
| Sauvegardes | Scripts, empreintes, rotation | Copie hors site chiffrée, test de restauration |
| Mises à jour | — | Système, Docker et SoluGation, régulièrement |
| Supervision | Sondes de santé, redémarrage automatique | Alerte si le site ne répond plus |
| Polices et ressources | Tout est servi par l'installation : aucun appel à un service tiers | — |
