# Développement

## Architecture

| Couche | Technologie | Emplacement |
|---|---|---|
| API | Django 5.2 + Django REST Framework | `backend/` |
| Base | PostgreSQL 17 | service `postgres` |
| Fichiers | Stockage S3 (django-storages) | service `stockage` |
| PDF | WeasyPrint (texte stocké → PDF, jamais d'IA dans le rendu) | `backend/apps/rapports/` |
| IA | Couche d'abstraction, API compatible OpenAI | `backend/apps/ai/provider.py` |
| Interface | React 19, Vite, Tailwind CSS v4, TanStack Query, React Router | `frontend/` |
| Thème | Fichier unique de jetons de design (couleurs, rayons, flous) | `frontend/src/styles/theme.css` |

### Applications Django (`backend/apps/`)

| Application | Contenu |
|---|---|
| `core` | Modèles de base (`TenantModel`, `ProjetModel`, `ValidationHumaineModel`, `FichierModel`), règles d'accès (`api/acces.py`), classes d'API (`api/base.py`), journalisation |
| `comptes` | Organisations, utilisateurs, rôles, authentification |
| `referentiels` | Référentiels, mesures, correspondances, importeurs |
| `projets` | Projets, acteurs, checklist, évaluations, tableau de bord, réglages, calendrier |
| `documents` | Dépôts, preuves, contrôle des fichiers |
| `suivi` | Plan d'action, tâches, commentaires, notifications, réunions |
| `ai` | Fournisseurs, analyse documentaire, recommandations, administration de l'IA |
| `ebios` | Ateliers EBIOS RM, propositions de l'IA |
| `risques` | Risques résiduels, dérogations |
| `scans` | Rapports de scan et constats |
| `rapports` | Instantané, rédaction, PDF, comparaison |
| `audit` | Journal d'audit en ajout seul et chaîné |

## Règles à respecter

1. **Isolation** : tout objet rattaché à un projet hérite de `ProjetModel`. Ses clés étrangères vers d'autres objets de projet sont listées dans `champs_meme_projet`. Les vues héritent de `ProjetScopedViewSet`, les serializers de `ProjetScopedSerializer` (contrôle du projet, des droits d'écriture et des relations multiples).
2. **Droits** : passer par `apps/core/api/acces.py` (`peut_ecrire_projet`, `peut_decider_projet`, `peut_administrer_projet`, `peut_prononcer_homologation`). Ne jamais réécrire une règle d'accès ailleurs.
3. **Journal** : toute écriture passe par `JournaliseMixin` (automatique dans `ProjetScopedViewSet`) ou `journaliser()`. Jamais d'écriture directe dans `JournalAudit` hors `JournalAudit.enregistrer()`.
4. **IA** : toute conclusion hérite de `ValidationHumaineModel` (naît `a_valider`) ; tout appel passe par `obtenir_fournisseur()` ; les entrées sont minimisées et les sorties filtrées.
5. **Fichiers** : contrôle par `documents.validation.controler()` (type réel, taille, empreinte) ; nom régénéré par `chemin_fichier`.
6. **Notifications** : `suivi.notifications.notifier()` (après validation de la transaction, un mail par destinataire, jamais à l'auteur).
7. **Interface** : couleurs et rayons uniquement via les jetons de `theme.css` ; statuts toujours doublés d'un libellé ou d'une icône (accessibilité) ; textes en français.
8. **Tests** : tout ce qui touche à l'isolation ou aux droits a ses tests (une autre organisation ne voit rien, un auditeur n'écrit rien).

## Ajouter une fonctionnalité : exemple complet

Ajoutons un registre des **incidents** de sécurité d'un projet.

### 1. Le modèle

`backend/apps/suivi/models.py` (ou une nouvelle application déclarée dans `INSTALLED_APPS`) :

```python
class Incident(ProjetModel):
    class Gravite(models.TextChoices):
        MINEURE = "mineure", "Mineure"
        MAJEURE = "majeure", "Majeure"

    titre = models.CharField(max_length=200)
    survenu_le = models.DateTimeField()
    gravite = models.CharField(max_length=10, choices=Gravite.choices)
    tache = models.ForeignKey("suivi.Tache", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    champs_meme_projet = ("tache",)  # la tâche liée doit être du même projet

    def __str__(self):
        return self.titre  # lisible dans le journal d'audit
```

```bash
docker compose exec backend python manage.py makemigrations suivi -n incidents
docker compose exec backend python manage.py migrate
```

### 2. L'API

```python
class IncidentSerializer(ProjetScopedSerializer):
    class Meta:
        model = Incident
        exclude = ["organisation"]


class IncidentViewSet(ProjetScopedViewSet):
    """Incidents d'un projet (`?projet=`). Isolation, droits et journal : hérités."""
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer
```

Déclaration dans `backend/config/api.py` : `routeur.register("incidents", IncidentViewSet, basename="incident")`.

### 3. Les tests d'isolation (obligatoires)

```python
class IncidentTests(BaseApi):
    def test_isolation(self):
        projet = self.creer_projet(self.api_a)
        r = self.api_a.post("/api/incidents/", {"projet": str(projet.id), "titre": "Phishing", "gravite": "mineure",
                                                "survenu_le": "2026-10-01T10:00:00Z"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.api_b.get(f"/api/incidents/{r.data['id']}/").status_code, 404)
        self.assertEqual(self.api_b.post("/api/incidents/", {"projet": str(projet.id), "titre": "x", "gravite": "mineure",
                                                             "survenu_le": "2026-10-01T10:00:00Z"}, format="json").status_code, 400)
```

`BaseApi` (`apps/core/tests/test_api.py`) fournit deux organisations, leurs clients API et des référentiels.

### 4. L'interface

- Types dans `frontend/src/api/types.ts`, hooks dans `frontend/src/api/hooks.ts` (le hook générique `useObjets(projetId, "incidents")` et `useEnregistrerObjet` suffisent souvent).
- Une page dans `frontend/src/pages/`, déclarée dans `frontend/src/main.tsx`, et une entrée dans `RUBRIQUES` (`frontend/src/composants/Disposition.tsx`).
- Le composant générique `ListeObjets` (`frontend/src/composants/ebios/Objets.tsx`) affiche une liste avec formulaire à partir d'une simple configuration de champs.

### 5. La documentation

Mettre à jour le [guide de l'utilisateur](06-guide-utilisateur.md) et, si des droits changent, [rôles et droits](09-roles-et-droits.md).

## Ajouter un référentiel

1. Créer `backend/apps/referentiels/importeurs/mon_referentiel.py`, une classe héritant d'`Importeur` : `code`, `nom`, `version`, `editeur`, `licence`, `url` (téléchargement automatique) ou `nom_fichier` / `fichiers_attendus` (dépôt manuel), et la méthode `lire(chemin)` qui renvoie des `MesureImportee`.
2. L'enregistrer dans `IMPORTEURS` (`importeurs/__init__.py`).
3. Écrire un test d'import sur un extrait.
4. Respecter les licences : pas de texte d'une norme payante dans le dépôt, jamais généré de mémoire ; une copie licenciée passe par `prive = True` (dépôt sous `data/private/`, `--organisation` obligatoire).

## Ajouter un fournisseur d'IA

Si son API est compatible OpenAI : rien à coder, il se configure à l'écran. Sinon : une classe héritant de `Fournisseur` dans `backend/apps/ai/provider.py` (méthodes `verifier_configuration()` et `completer_json(systeme, utilisateur)` renvoyant un `ReponseIA`), branchée dans `obtenir_fournisseur()`. Ne jamais journaliser le contenu envoyé ni la clé.

## Lancer les tests

```bash
docker compose exec backend python manage.py test
docker compose exec frontend npx tsc --noEmit -p .
```

Le fournisseur `factice` (hors ligne) et un fournisseur « scripté » dans les tests permettent de tester toute la chaîne IA sans réseau.

## Conventions

- Code, interface, messages et commits **en français**.
- Un commit par étape, message clair.
- Commentaires rares et utiles : le *pourquoi*, pas le *quoi*.
