# Avant publication : feuille de route

État au 02/11/2026. Ce qui manque avant de rendre SoluGation disponible publiquement, par priorité.

## Bloquant

| Sujet | Pourquoi | À faire |
|---|---|---|
| Licence | Aucune licence = personne n'a le droit d'utiliser le code | Choisir (recommandé : AGPL-3.0 + licence commerciale + CLA) et ajouter `LICENSE` |
| Fichiers du dépôt | Attendus de tout projet open source | `SECURITY.md` (contact de signalement), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, modèles de tickets |
| Historique Git | Un secret commité par erreur reste dans l'historique ; l'email d'auteur devient public | Scan `gitleaks` de tout l'historique ; choisir l'email d'auteur ; vérifier qu'aucun texte ISO ni PDF source n'a été commité |
| Sources des référentiels | Certaines licences imposent attribution ou partage à l'identique (OWASP ASVS en CC BY-SA) | Citer les sources dans l'appli et le dépôt, ne pas redistribuer les PDF déposés à la main. Vérifié : guide d'hygiène ANSSI (Licence Ouverte Etalab V1, mention en dernière page du PDF), NIST (domaine public, CC0 hors États-Unis). |

## Fortement recommandé

| Sujet | À faire |
|---|---|
| Supervision | Alerte externe si le site ne répond plus ; exporter les journaux |
| Poids de l'interface | Découper le paquet JavaScript principal (environ 620 ko) |
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

## Fait

| Sujet | Où |
|---|---|
| Déploiement de production : gunicorn, interface compilée, HTTPS automatique (Caddy), services internes non exposés, démarrage refusé sur configuration dangereuse | [Production](15-production.md) |
| Sauvegardes et restauration (base + fichiers, empreintes, rotation), testées | [Production, sauvegardes](15-production.md#6-sauvegardes) |
| Service de tâches : analyses IA hors du serveur web, rappels planifiés sans cron | `executer_taches` |
| Aucune ressource tierce (police embarquée), CSP stricte | [Sécurité](10-securite.md) |
| Gestion des comptes : invitation par mail, rôle, désactivation, mot de passe oublié | [Guide, comptes](06-guide-utilisateur.md#comptes) |
| Écran « Mon compte » : profil, changement de mot de passe, déconnexion sur mobile | [Guide, mon compte](06-guide-utilisateur.md#mon-compte) |
| Double authentification (TOTP, codes de secours), politique au choix de l'installateur ; limites de tentatives partagées entre processus | [Guide](06-guide-utilisateur.md#double-authentification), [configuration](03-configuration.md#sécurité-des-comptes) |

## Référentiels libres candidats (licences vérifiées le 02/11/2026)

| Référentiel | Licence | Intégrable |
|---|---|---|
| Mesures de MonServiceSécurisé (ANSSI, homologation des services publics en ligne) | Apache-2.0 (dépôt `betagouv/mon-service-securise`) | **Intégré** (`monservicesecurise`) |
| NIST SP 800-53 r5 (+ bases 800-53B), format OSCAL | Domaine public / CC0 | Oui |
| Règlement d'exécution (UE) 2024/2690 (mesures NIS2), DORA, RGPD art. 32 | Textes officiels de l'UE, réutilisables | Oui, en citant EUR-Lex |
| OWASP MASVS (applications mobiles) | CC BY-SA, comme l'ASVS | Oui, avec attribution et partage à l'identique |
| Guide CNIL de la sécurité des données personnelles (2024) | CC BY-ND d'après la page « Informations publiques » de la CNIL | Oui sans modifier les intitulés ; à confirmer sur le guide |
| SecNumCloud 3.2 | Document public, licence non trouvée (téléchargement automatique refusé) | À vérifier sur le PDF |
| BSI IT-Grundschutz | Catalogue Grundschutz++ en CC BY-SA d'après une source tierce ; Kompendium sous accord de licence | À vérifier auprès du BSI |
| CIS Controls v8.1 | CC BY-NC-ND, usage commercial soumis à accord du CIS | Non (version commerciale) |
| PCI DSS, SOC 2, ISO 2700x | Propriétaires | Non : copie licenciée du client uniquement |

## Juridique

| Sujet | À faire |
|---|---|
| Marque « SoluGation » | Recherche d'antériorité (INPI, EUIPO), dépôt éventuel |
| Mentions | Avertissement : aucune conclusion de l'outil ne vaut décision d'homologation |
| Données personnelles | Registre de traitement type et notice pour les organisations qui installent l'outil |
