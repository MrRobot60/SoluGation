# Dépannage

Commencez toujours par :

```bash
docker compose ps                         # quels services tournent, lesquels sont « unhealthy »
docker compose logs --tail=100 backend    # erreurs du serveur (idem : frontend, postgres, stockage)
curl -s http://localhost:8000/api/sante/  # répond {"statut": "ok", …} si l'API tourne
```

## Démarrage et installation

| Symptôme | Cause probable | Solution |
|---|---|---|
| `docker compose` : commande inconnue (macOS, Colima) | Greffon Compose non déclaré | Dans `~/.docker/config.json` : `"cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]` |
| `Cannot connect to the Docker daemon` | Colima / Docker arrêté | `colima start` (ou démarrer Docker Desktop) |
| `port is already allocated` | Un autre service utilise 5432, 5173, 8000, 8333 ou 8025 | Arrêter ce service, ou changer le port côté hôte dans `docker-compose.yml` (`"127.0.0.1:5433:5432"`) |
| Le serveur s'arrête au démarrage, `password authentication failed` | Mot de passe différent entre `POSTGRES_PASSWORD` et `DATABASE_URL` | Les aligner. Si la base a déjà été créée avec l'ancien mot de passe : le changer dans PostgreSQL, ou `docker compose down -v` (efface tout) |
| `Stockage S3 injoignable` | SeaweedFS pas encore prêt ou mal configuré | `docker compose logs stockage` ; vérifier `S3_ENDPOINT_URL=http://stockage:8333` et des clés de 8 caractères minimum |
| `DisallowedHost` / erreur 400 | Nom d'hôte absent de `DJANGO_ALLOWED_HOSTS` | L'ajouter (garder `backend`) |
| Erreur CSRF à la connexion | Origine de l'interface absente de `DJANGO_CSRF_TRUSTED_ORIGINS` | Ajouter l'adresse exacte, schéma compris (`http://localhost:5173`) |
| Une modification de `.env` n'a pas d'effet | `docker compose restart` ne relit pas `.env` | `docker compose up -d` |
| L'interface reste blanche ou ne se met pas à jour | Premier `npm ci` en cours, ou cache Vite | `docker compose logs -f frontend` ; sinon `docker compose restart frontend` |
| `ModuleNotFoundError` après une mise à jour | Nouvelle dépendance Python | `docker compose build backend && docker compose up -d` |
| Erreur 500 passagère pendant le développement | Rechargement automatique du serveur Django | Réessayer quelques secondes plus tard |

## Comptes et connexion

| Symptôme | Solution |
|---|---|
| Mot de passe oublié | `docker compose exec backend python manage.py changepassword email@exemple.fr` (pas encore de réinitialisation par mail) |
| « Le serveur est injoignable » sur l'interface | L'API ne répond pas : voir les journaux du `backend` |
| Connecté mais aucun projet | Vous n'êtes acteur d'aucun projet : créez-en un, ou demandez à être ajouté (Réglages du projet → Acteurs) |
| Pas d'entrée « Administration » | Réservée aux administrateurs d'organisation et de l'installation (`creer_organisation --admin-installation`, ou l'admin Django) |
| Trop de tentatives de connexion | Attendre une minute (limite de 10 par minute) |

## Référentiels

| Symptôme | Solution |
|---|---|
| `importer_referentiel` : fichier introuvable (II 901, RGS) | Déposer les PDF dans `data/sources/<code>/<version>/` (voir [référentiels](08-referentiels.md)) |
| Échec de téléchargement (NIST, OWASP, ANSSI) | Vérifier l'accès Internet du conteneur ; relancer plus tard ; ou télécharger le fichier et passer `--fichier` |
| ISO : « préciser --organisation » | La copie licenciée est privée : `--organisation <slug>` |
| ISO : « Colonnes attendues » | En-tête du CSV : `identifiant;intitule;categorie;texte`, encodage UTF-8 |

## Documents et fichiers

| Symptôme | Cause | Solution |
|---|---|---|
| « Type de fichier non autorisé » | Contenu réel hors liste blanche (l'extension ne suffit pas) | Convertir en PDF, Office, OpenDocument, texte, CSV, XML, PNG ou JPEG |
| « Document contenant des macros : refusé » | Fichier `.docm`/`.xlsm` ou macros embarquées | Enregistrer sans macros |
| « Fichier trop volumineux » | Au-delà de `UPLOAD_MAX_MO` | Augmenter la limite (et celle du proxy en production) ou découper |
| Document « non analysé » par l'IA | Image ou PDF scanné sans couche texte | Pas de reconnaissance de caractères en V1 : fournir un PDF texte |

## Intelligence artificielle

| Message | Cause | Solution |
|---|---|---|
| Aucun bouton IA | Aucune IA configurée, ou désactivée pour l'organisation | Administration → Intelligence artificielle ; vérifier « Autoriser l'IA pour cette organisation » |
| « … l'administrateur n'a pas accepté la responsabilité … » | Acceptation absente | Écran : cocher la case puis activer ; fichier : `IA_ZDR_CONFIRME=True` |
| « Adresse interne refusée » | Protection SSRF (IA sur le réseau local) | `IA_AUTORISER_RESEAU_LOCAL=True` dans `.env`, puis `docker compose up -d` |
| « HTTPS obligatoire » | Adresse en `http://` | Utiliser `https://`, ou autoriser le réseau local |
| « … a refusé la requête (HTTP 401) » | Clé absente ou invalide | Ressaisir la clé, **Tester la connexion** |
| HTTP 404 | Adresse ou modèle inexact | L'adresse se termine en général par `/v1` ; vérifier l'identifiant exact du modèle |
| HTTP 429 | Quota du fournisseur | Patienter (nouvelles tentatives automatiques) ou relever le quota |
| « Réponse … illisible » / « pas au format JSON attendu » | Modèle trop petit ou sans mode JSON | Choisir un modèle qui gère le mode JSON |
| Clé enregistrée mais l'IA échoue après un changement de `DJANGO_SECRET_KEY` | La clé chiffrée ne se déchiffre plus | Ressaisir la clé (ou fixer `IA_CLE_CHIFFREMENT`) |
| Analyse « en cours » qui ne finit jamais | Le serveur a redémarré pendant l'analyse | Relancer l'analyse (une analyse est considérée abandonnée après 30 minutes) |

## Mails

| Symptôme | Solution |
|---|---|
| Aucun mail en développement | Ils sont dans Mailpit : <http://localhost:8025> |
| Aucun mail en production | Vérifier `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, les identifiants ; les journaux du `backend` (« Échec d'envoi ») |
| Pas de notification pour un projet | Réglages du projet → Notifications désactivées |
| L'invitation n'apparaît pas dans l'agenda | Ouvrir la pièce jointe `invitation.ics` ; certains webmails l'ajoutent seulement à l'ouverture |

## Rapports PDF

| Symptôme | Solution |
|---|---|
| Polices manquantes ou erreur WeasyPrint | Reconstruire l'image : `docker compose build backend` (Pango et polices sont installés dans le `Dockerfile`) |
| « Rédaction par l'IA en cours » qui dure | Patienter ; sinon le texte automatique reste disponible et le rapport peut être relu |
| « Un rapport validé ne se modifie plus » | Normal : générer une nouvelle version |

## Journal d'audit

| Symptôme | Que faire |
|---|---|
| « Anomalie à l'entrée n° X » à la vérification d'intégrité | **Ne rien corriger.** Conserver l'export et la date ; alerter le RSSI : une entrée a été modifiée ou supprimée directement en base. Comparer avec la dernière empreinte conservée hors application. |
| Erreur « Le journal d'audit est en ajout seul » | Normal : aucune modification ni suppression n'est possible, y compris dans l'admin |

## Obtenir de l'aide

Joignez : la version (`git log -1 --oneline`), la sortie de `docker compose ps`, les dernières lignes de `docker compose logs backend`, et **jamais** le contenu de `.env`.
