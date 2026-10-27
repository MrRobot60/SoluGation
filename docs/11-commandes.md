# Commandes et tâches planifiées

Toutes les commandes se lancent dans le conteneur du serveur :

```bash
docker compose exec backend python manage.py <commande> [options]                # développement
docker compose -f docker-compose.prod.yml --env-file .env.production exec backend python manage.py <commande>   # production (alias « sg », voir 15-production)
```

## Installation et comptes

| Commande | Effet |
|---|---|
| `creer_organisation --nom NOM --email EMAIL [--secteur public\|prive] [--prenom P] [--nom-famille N] [--admin-installation]` | Crée une organisation et son premier administrateur. `--admin-installation` : administrateur de toute l'installation (IA, admin Django). |
| `creer_utilisateur --organisation SLUG --email EMAIL [--role admin\|membre\|auditeur] [--prenom P] [--nom-famille N] [--fonction F]` | Ajoute un compte. `auditeur` = lecture seule partout. |
| `createsuperuser` | Commande Django standard : un compte d'administration technique, sans organisation (accès à `/admin` seulement). |
| `changepassword EMAIL` | Change le mot de passe d'un compte. |
| `creer_demo` | Données de démonstration (développement uniquement). |

**Mot de passe** : jamais en argument (il resterait dans l'historique du shell). Il est demandé deux fois de façon masquée, ou lu dans la variable `SOLUGATION_MOT_DE_PASSE` pour une installation automatisée :

```bash
SOLUGATION_MOT_DE_PASSE='…' docker compose exec -e SOLUGATION_MOT_DE_PASSE backend python manage.py creer_utilisateur --organisation mon-organisation --email rssi@exemple.fr
```

Le **slug** d'une organisation est son nom en minuscules sans accents ni espaces (« Mairie de Lyon » → `mairie-de-lyon`). Il est affiché par `creer_organisation` et dans l'admin Django.

## Référentiels

| Commande | Effet |
|---|---|
| `importer_referentiel libres` | Importe (ou met à jour) tous les référentiels libres. |
| `importer_referentiel CODE [--fichier CHEMIN]` | Un seul : `nist-csf`, `owasp-asvs`, `hygiene-anssi`, `ii901`, `rgs`. |
| `importer_referentiel iso27001 --organisation SLUG --fichier /data/private/iso27001.csv` | Copie licenciée ISO 27001, visible de cette seule organisation. |

Voir [les référentiels](08-referentiels.md) pour les fichiers attendus.

## Stockage

| Commande | Effet |
|---|---|
| `initialiser_stockage [--attente 30]` | Crée le bucket S3 et active le versioning (lancé à chaque démarrage, sans effet s'il existe). |
| `sauvegarder_stockage DOSSIER` | Copie tous les fichiers du bucket dans `DOSSIER` (vide), avec `inventaire.json` (SHA-256 de chaque fichier). Utilisée par `scripts/sauvegarder.sh`. |
| `restaurer_stockage DOSSIER` | Remet les fichiers d'une sauvegarde dans le bucket, après vérification de **toutes** les empreintes. |

## Production

| Commande | Effet |
|---|---|
| `check --deploy --tag security` | Contrôles de configuration (valeurs d'exemple, domaine, SMTP, chiffrement) ; lancée à chaque démarrage du serveur de production, qui refuse de démarrer en cas d'erreur. |
| `executer_taches [--intervalle 3] [--une-fois]` | Service de tâches (conteneur `taches`) : exécute les analyses IA en attente et les tâches planifiées ci-dessous. |
| `scripts/sauvegarder.sh` / `scripts/restaurer.sh DOSSIER` | Scripts de l'hôte (pas de `manage.py`) : voir [sauvegardes](15-production.md#6-sauvegardes). |

## Tâches à planifier

En **production**, le service `taches` les exécute lui-même (au démarrage, puis à la fréquence indiquée) : rien à planifier. En **développement**, lancez-les à la main pour tester.

| Commande | Fréquence conseillée | Effet |
|---|---|---|
| `rappeler_reunions` | toutes les heures | Rappel (appli et mail) des réunions des 24 prochaines heures, une seule fois. |
| `rappeler_revues` | chaque jour | Rappel 30 jours avant la revue périodique, puis en cas de retard, une fois par échéance. |
| `expirer_derogations` | chaque jour | Passe « expirées » les dérogations dont la date est dépassée (c'est aussi vérifié à chaque consultation). |

Sans le service `taches` (installation hors Docker), planifiez-les avec cron :

```cron
0 * * * *  cd /opt/solugation && docker compose exec -T backend python manage.py rappeler_reunions
15 6 * * * cd /opt/solugation && docker compose exec -T backend python manage.py rappeler_revues
20 6 * * * cd /opt/solugation && docker compose exec -T backend python manage.py expirer_derogations
```

## Tests

```bash
docker compose exec backend python manage.py test            # toute la suite (isolation, sécurité, fonctions)
docker compose exec backend python manage.py test apps.risques   # une application
docker compose exec frontend npx tsc --noEmit -p .           # vérification des types de l'interface
```

## Administration Django

<http://localhost:8000/admin/> : accès pour les comptes « staff » (dont l'administrateur de l'installation). Utile pour gérer les comptes (désactiver, changer d'organisation ou de rôle) tant qu'il n'existe pas d'écran dédié dans l'interface. Le journal d'audit y est en lecture seule.

## API

L'interface s'appuie entièrement sur une API REST, documentée automatiquement :

| Adresse | Contenu |
|---|---|
| `/api/docs/` | Documentation interactive (Swagger) |
| `/api/schema/` | Schéma OpenAPI |
| `/api/sante/` | Sonde de disponibilité (`{"statut": "ok"}`) |

L'authentification se fait par session (cookie) avec protection CSRF : appelez d'abord `GET /api/auth/csrf/`, puis `POST /api/auth/connexion/` avec l'en-tête `X-CSRFToken`. Les mêmes règles d'isolation et de droits s'appliquent qu'à l'écran.
