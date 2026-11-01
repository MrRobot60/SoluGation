# SoluGation

**SoluGation** pilote l'homologation de sécurité d'un bien (application, poste de travail, système d'information) de bout en bout : référentiels, checklist documentaire, évaluation des mesures, plan d'action, suivi collaboratif, analyse de risques EBIOS RM, risques résiduels et dérogations, réunions, rapport d'état des lieux en PDF, jusqu'à la décision de l'autorité d'homologation.

L'intelligence artificielle est **facultative** : sans configuration, tout fonctionne sans elle. Si l'administrateur branche un fournisseur (n'importe quelle API compatible OpenAI, ou un modèle local), l'IA **propose** et un humain **valide** toujours.

SoluGation s'installe chez soi ou dans son système d'information (auto-hébergement, Docker).

## Démarrage rapide (poste de développement ou d'évaluation)

```bash
git clone <adresse-du-dépôt> solugation && cd solugation
cp .env.example .env        # puis remplacer toutes les valeurs « a-remplacer »
docker compose up -d        # base, stockage, mails de test, serveur, interface
docker compose exec backend python manage.py importer_referentiel libres
docker compose exec backend python manage.py creer_organisation --nom "Mon organisation" --email moi@exemple.fr --admin-installation
```

Puis ouvrir <http://localhost:5173> et se connecter. Les mails envoyés sont visibles sur <http://localhost:8025>.

Le détail (prérequis, choix des valeurs, référentiels à déposer à la main) est dans [l'installation](docs/02-installation.md).

## En production

Serveur Linux avec Docker, nom de domaine, ports 80 et 443 : HTTPS automatique, aucun service interne exposé, tâches planifiées et sauvegardes fournies.

```bash
cp .env.production.example .env.production   # domaine, secrets, SMTP
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build --wait
```

Pas à pas : [Déployer en production](docs/15-production.md), y compris sur un serveur interne d'entreprise sans accès à Internet (certificat de l'organisation, derrière un répartiteur de charge).

Pour simplement faire essayer l'outil, sans serveur ni nom de domaine : `scripts/essai-cloudflare.sh demarrer` (tunnel Cloudflare gratuit, données fictives uniquement).

## Documentation

| | |
|---|---|
| [Présentation](docs/01-presentation.md) | Ce que fait SoluGation, le parcours d'une homologation, le vocabulaire |
| [Installation](docs/02-installation.md) | Docker, premier démarrage, mise à jour, sauvegarde |
| [Configuration](docs/03-configuration.md) | Toutes les variables du fichier `.env` |
| [Premiers pas](docs/04-premiers-pas.md) | Organisation, comptes, référentiels, données de démonstration |
| [Tutoriel](docs/05-tutoriel.md) | Une homologation complète, pas à pas |
| [Guide de l'utilisateur](docs/06-guide-utilisateur.md) | Chaque écran, chaque bouton |
| [Intelligence artificielle](docs/07-ia.md) | Brancher un fournisseur, confidentialité, fonctionnement sans IA |
| [Référentiels](docs/08-referentiels.md) | Import, copie licenciée ISO 27001, correspondances |
| [Rôles et droits](docs/09-roles-et-droits.md) | Qui peut faire quoi |
| [Sécurité](docs/10-securite.md) | Isolation, chiffrement, journal d'audit, fichiers déposés |
| [Commandes et tâches planifiées](docs/11-commandes.md) | Ligne de commande, cron, API |
| [Dépannage](docs/12-depannage.md) | Problèmes fréquents et solutions |
| [Développement](docs/13-developpement.md) | Architecture, ajouter une fonctionnalité, tests |
| [Déployer en production](docs/15-production.md) | Serveur HTTPS, configuration, sauvegardes, mises à jour |

## Licence

SoluGation est un logiciel libre, sous **double licence** :

- [GNU AGPL-3.0](LICENSE) : libre et gratuit, y compris pour un usage commercial ; toute version modifiée, même seulement
  proposée en ligne, doit publier son code source sous la même licence ;
- [licence commerciale](LICENCE-COMMERCIALE.md) : pour une intégration sans les obligations de l'AGPL, ou avec support
  et garanties contractuels. Contact : solugation@mail.fr.

Sources des référentiels et composants tiers : [NOTICE](NOTICE).

## Contribuer et signaler une faille

- Contribuer : [CONTRIBUTING.md](CONTRIBUTING.md) (contributions acceptées sous l'[accord de contribution](CLA.md)).
- Vulnérabilité : **pas de ticket public**, écrire à solugation@mail.fr ([SECURITY.md](SECURITY.md)).
