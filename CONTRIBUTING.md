# Contribuer à SoluGation

Merci ! Toute contribution est bienvenue : correctif, fonctionnalité, documentation, référentiel, traduction, retour
d'usage.

## Avant de commencer

- **Faille de sécurité** : ne publiez pas de ticket, suivez [SECURITY.md](SECURITY.md).
- **Bogue ou idée** : ouvrez un ticket avec le modèle proposé ; pour une fonctionnalité importante, discutons-en avant
  d'écrire le code.
- **Accord de contribution** : chaque contribution est acceptée sous l'[accord de contribution](CLA.md), qui permet de
  distribuer SoluGation sous AGPL-3.0 et sous licence commerciale. Vous restez propriétaire de votre code.

## Environnement

Installation de développement (Docker) : [docs/02-installation.md](docs/02-installation.md). Architecture, règles et
exemple complet d'ajout de fonctionnalité : [docs/13-developpement.md](docs/13-developpement.md).

```bash
docker compose exec backend python manage.py test     # toute la suite
docker compose exec frontend npx tsc --noEmit -p .   # types de l'interface
```

## Règles non négociables

1. **Isolation entre organisations** : toute donnée est filtrée par organisation et par projet ; toute nouvelle ressource
   est accompagnée de tests prouvant qu'une autre organisation ne la voit ni ne la modifie.
2. **L'IA recommande, l'humain valide** : une conclusion de l'IA naît « à valider » ; aucune ne vaut décision.
3. **Journal d'audit** : toute écriture est tracée ; le journal reste en ajout seul.
4. **Droits d'auteur des référentiels** : aucun texte de norme payante (ISO ou autre) dans le dépôt, ni généré de mémoire ;
   un référentiel libre s'importe depuis sa source officielle, avec sa licence, sa version et son empreinte.
5. **Secrets** : rien dans le dépôt (`.env` et ses variantes sont ignorés). Aucune donnée réelle de client dans les tests
   ou les exemples.

## Conventions

- Code, interface, messages et documentation **en français**.
- Un commit par étape, message clair, à l'indicatif (« Ajoute… », « Corrige… »).
- Commentaires rares et utiles : le *pourquoi*, pas le *quoi*.
- Interface : couleurs et rayons uniquement via `frontend/src/styles/theme.css` ; statuts toujours doublés d'un libellé
  ou d'une icône (accessibilité) ; écrans utilisables sur mobile.
- Documentation mise à jour dans `docs/` (elle alimente la rubrique Aide de l'appli).

## Demande de fusion

- Une demande = un sujet.
- Tests ajoutés ou mis à jour, suite complète au vert.
- Décrire le changement, son impact sur la sécurité et l'isolation, et comment le vérifier.
