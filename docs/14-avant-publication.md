# Avant publication : feuille de route

État au 27/10/2026. Ce qui manque avant de rendre SoluGation disponible publiquement, par priorité.

## Bloquant

| Sujet | Pourquoi | À faire |
|---|---|---|
| Déploiement de production | Le `docker-compose.yml` actuel sert au développement (serveur Django de dev, Vite en mode dev) | Fichier Compose de production : gunicorn, interface construite (`npm run build`) servie par le proxy, proxy TLS (Caddy ou Traefik), limite de taille d'envoi au proxy ; l'image de l'interface doit embarquer `docs/` (rubrique Aide) |
| Sauvegardes | Aucune sauvegarde automatisée | Sauvegarde planifiée de PostgreSQL et du stockage, procédure de restauration testée |
| Tâches de fond | Mails et IA tournent dans des threads du serveur : perdus en cas de redémarrage | File de tâches (Celery ou RQ + Redis), limites de débit partagées entre processus |
| Comptes | Pas d'écran de gestion des utilisateurs, ni de réinitialisation de mot de passe par mail | Écran d'administration des comptes, mot de passe oublié, invitation par mail |
| Licence | Aucune licence = personne n'a le droit d'utiliser le code | Choisir (recommandé : AGPL-3.0 + licence commerciale + CLA) et ajouter `LICENSE` |
| Fichiers du dépôt | Attendus de tout projet open source | `SECURITY.md` (contact de signalement), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, modèles de tickets |
| Historique Git | Un secret commité par erreur reste dans l'historique ; l'email d'auteur devient public | Scan `gitleaks` de tout l'historique ; choisir l'email d'auteur ; vérifier qu'aucun texte ISO ni PDF source n'a été commité |
| Sources des référentiels | Certaines licences imposent attribution ou partage à l'identique (OWASP ASVS en CC BY-SA) | Vérifier chaque licence, citer les sources, ne pas redistribuer les PDF déposés à la main |

## Fortement recommandé

| Sujet | À faire |
|---|---|
| Double authentification | TOTP pour tous, obligatoire pour les administrateurs |
| Durée de session | Réduire (8 h) et déconnexion après inactivité |
| Base de données | Rôle PostgreSQL applicatif qui n'est pas propriétaire des tables (le trigger du journal ne peut alors plus être désactivé par l'application) |
| Chiffrement au repos | Documenté mais à vérifier en conditions réelles (`S3_SSE`, disques chiffrés) |
| Intégration continue | Tests backend, vérification TypeScript, `pip-audit`, `npm audit`, scan d'images à chaque commit |
| Images publiées | Images Docker versionnées (GitHub Container Registry) pour installer sans construire |
| Tests de l'interface | Tests de composants et parcours de bout en bout (Playwright) |
| Accessibilité | Audit RGAA / WCAG (clavier, lecteurs d'écran, contrastes) |
| Mobile | Administration et Bibliothèque accessibles depuis la barre mobile |
| Ancrage du journal | Export périodique de la dernière empreinte hors de l'application, pour détecter une troncature |

## Fonctionnel à compléter

| Sujet | État |
|---|---|
| Format Cyberwatch | Import CSV générique en place, à valider sur un vrai export |
| Réutilisation des preuves via les correspondances | Correspondances saisissables, pas encore exploitées pour propager une preuve |
| Migration vers une nouvelle version de référentiel | Alerte affichée, pas de migration des évaluations |
| Constats de scan dans le rapport PDF | Non inclus |
| Synchronisation Outlook (Microsoft Graph) | Repoussée après le cœur du produit |
| Réunions | Pas de réponse de participation (RSVP), pas d'annulation envoyée à un participant retiré |
| Reconnaissance de caractères | PDF scannés non analysés par l'IA |
| Mascotte | À fournir |

## Juridique

| Sujet | À faire |
|---|---|
| Marque « SoluGation » | Recherche d'antériorité (INPI, EUIPO), dépôt éventuel |
| Mentions | Avertissement : aucune conclusion de l'outil ne vaut décision d'homologation |
| Données personnelles | Registre de traitement type et notice pour les organisations qui installent l'outil |
