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

## Production

| Symptôme | Cause | Solution |
|---|---|---|
| Le serveur redémarre en boucle, `solugation.E00x` dans `sg logs backend` | Valeur d'exemple ou réglage manquant | Corriger `.env.production` (voir [production](15-production.md#si-le-serveur-ne-démarre-pas)), puis `sg up -d` |
| `SOLUGATION_DOMAINE manquant` au lancement | Compose lancé sans le fichier de configuration | Ajouter `--env-file .env.production` (ou utiliser l'alias `sg`) |
| Pas de certificat, erreur TLS dans `sg logs proxy` | DNS pas encore propagé, port 80 fermé, ou pas d'accès Internet | Vérifier `dig +short <domaine>` et le pare-feu ; sur réseau interne, fournir votre certificat |
| Erreur 413 à l'envoi d'un document | Limite du proxy | Augmenter `SOLUGATION_ENVOI_MAX_MO` (et `UPLOAD_MAX_MO`), puis `sg up -d` |
| Erreur 502 | Serveur web arrêté ou en démarrage | `sg ps`, `sg logs backend` |
| Analyse IA « en attente » qui ne démarre pas | Service `taches` arrêté | `sg ps` ; `sg logs taches` ; `sg up -d taches` |
| Analyse marquée « interrompue » | Service `taches` arrêté pendant l'analyse | Relancer l'analyse |
| CSRF refusé à la connexion | Adresse d'accès différente du domaine (port, autre nom) | Accéder par `https://<SOLUGATION_DOMAINE>`, ou compléter `DJANGO_CSRF_TRUSTED_ORIGINS` |
| `restaurer.sh` : « Empreintes invalides » | Sauvegarde modifiée ou incomplète | Ne pas forcer : prendre la sauvegarde précédente |

## Comptes et connexion

| Symptôme | Solution |
|---|---|
| Mot de passe oublié | **Mot de passe oublié ?** sur la page de connexion. Sans mail possible : `docker compose exec backend python manage.py changepassword email@exemple.fr` |
| Mail d'invitation ou de réinitialisation non reçu | Vérifier les indésirables ; en dev, Mailpit (<http://localhost:8025>) ; vérifier `EMAIL_HOST` et `FRONTEND_URL` (adresse des liens). L'administrateur peut **renvoyer l'invitation** |
| « Ce lien n'est plus valable » | Lien déjà utilisé, expiré (1 h pour une réinitialisation, 7 jours pour une invitation), remplacé par un renvoi, ou compte désactivé : en demander un nouveau |
| Trop de demandes de lien | Limite de 5 demandes par heure et par adresse IP : patienter |
| « Le serveur est injoignable » sur l'interface | L'API ne répond pas : voir les journaux du `backend` |
| Connecté mais aucun projet | Vous n'êtes acteur d'aucun projet : créez-en un, ou demandez à être ajouté (Réglages du projet → Acteurs) |
| Pas d'entrée « Administration » | Réservée aux administrateurs d'organisation et de l'installation (un administrateur change votre rôle dans **Administration → Comptes**) |
| Trop de tentatives de connexion | Attendre une minute (limite de 10 par minute) |
| Double authentification : « Code incorrect » alors que le code est bon | L'heure du téléphone ou du serveur est fausse (±30 s tolérées) : activer l'heure automatique du téléphone, vérifier la synchronisation NTP du serveur. Un code déjà utilisé est aussi refusé : attendre le suivant |
| Double authentification : téléphone perdu | Se connecter avec un code de secours ; sinon l'administrateur de l'organisation **réinitialise** la double authentification (Administration → Comptes). Administrateur unique de l'installation bloqué : `docker compose exec backend python manage.py shell -c "from apps.comptes.models import Utilisateur; from apps.comptes.double_auth import desactiver; desactiver(Utilisateur.objects.get(email='admin@exemple.fr'))"` |
| Double authentification de tous les comptes en échec après un changement de `DJANGO_SECRET_KEY` | Les secrets ne se déchiffrent plus : fixer `SOLUGATION_CLE_CHIFFREMENT` à l'avance, ou réinitialiser chaque compte |
| Admin Django : renvoyé vers la page de connexion de SoluGation | Normal si la double authentification est active : se connecter par SoluGation (le code est demandé), puis rouvrir `/admin/` |

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
