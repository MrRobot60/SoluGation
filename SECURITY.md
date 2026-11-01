# Signaler une vulnérabilité

SoluGation sert à piloter des homologations de sécurité : nous prenons chaque signalement au sérieux.

**Ne publiez pas de ticket public pour une vulnérabilité.** Écrivez à **solugation@mail.fr** avec :

- la version concernée (`git log -1 --oneline`, ou la date de l'image) ;
- la description du problème et son impact ;
- les étapes pour le reproduire, ou une preuve de concept ;
- votre nom ou pseudonyme si vous souhaitez être remercié.

## Engagements

| Étape | Délai visé |
|---|---|
| Accusé de réception | 5 jours ouvrés |
| Première évaluation (gravité, périmètre) | 15 jours ouvrés |
| Correctif et publication coordonnée | selon la gravité, au plus tard 90 jours après le signalement |

Le projet est maintenu par une seule personne : ces délais sont des objectifs. Vous serez tenu informé de l'avancement
et crédité dans les notes de version, si vous le souhaitez.

## Règles

- Testez uniquement sur **votre propre installation** (la configuration de développement ou l'essai local suffisent) ;
  jamais sur l'installation d'un tiers sans son autorisation écrite.
- N'accédez pas aux données d'autrui, ne les modifiez pas, ne dégradez pas le service.
- Laissez-nous le temps de corriger avant toute publication.

## Versions prises en charge

Seule la dernière version publiée reçoit des correctifs de sécurité.

## Périmètre

Inclus : le code de ce dépôt (serveur, interface, configuration de déploiement fournie). Exclus : les installations
gérées par des tiers (adressez-vous à leur exploitant), les fournisseurs d'IA et hébergeurs choisis par l'administrateur.
