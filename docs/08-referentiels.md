# Référentiels

## Disponibles

| Code | Référentiel | Version | Licence | Import |
|---|---|---|---|---|
| `nist-csf` | NIST Cybersecurity Framework | 2.0 | Domaine public | Téléchargement automatique |
| `owasp-asvs` | OWASP Application Security Verification Standard | 5.0.0 | CC BY-SA | Téléchargement automatique |
| `hygiene-anssi` | Guide d'hygiène informatique (ANSSI) | 2.0 | Licence Ouverte | Téléchargement automatique |
| `ii901` | II 901 (protection des systèmes d'information sensibles) | 2015 | Libre | Fichier à déposer |
| `rgs` | Référentiel général de sécurité | 2.0 | Libre | Fichiers à déposer |
| `iso27001` | ISO/IEC 27001:2022, Annexe A | 2022 | **Propriétaire** | Copie licenciée de l'organisation |

Chaque import enregistre la source, la version, la date et l'**empreinte SHA-256** du fichier source (visibles dans la Bibliothèque).

## Importer

```bash
docker compose exec backend python manage.py importer_referentiel libres     # tous les libres
docker compose exec backend python manage.py importer_referentiel nist-csf   # un seul
```

L'import est **idempotent** : relancé, il met à jour les intitulés et textes sans dupliquer ni casser les évaluations existantes.

### Fichiers à déposer à la main

Le dossier `data/` du dépôt est monté dans le conteneur sous `/data`.

| Référentiel | Emplacement | Fichiers |
|---|---|---|
| II 901 | `data/sources/ii901/2015/` | `cir_39217.pdf` (Légifrance) |
| RGS | `data/sources/rgs/2.0/` | `RGS_v-2-00_Corps_du_texte.pdf`, `RGS_v-2-0_B1.pdf`, `RGS_v-2-0_B2.pdf`, `RGS_v-2-0_B3.pdf` (cyber.gouv.fr) |

Ou indiquez un fichier : `importer_referentiel ii901 --fichier /data/mon-dossier/cir_39217.pdf`.

`data/sources/` est exclu de Git : les sources se retéléchargent ou se redéposent.

## ISO 27001 : votre copie licenciée

ISO 27001 est une norme **payante** : SoluGation n'en fournit aucun texte et n'en génère pas. Vous importez **votre** copie, qui reste **privée à votre organisation** (invisible des autres, même sur la même installation).

1. Préparez un CSV UTF-8 (séparateur `;` ou `,`) avec les colonnes `identifiant;intitule;categorie;texte` :

   ```csv
   identifiant;intitule;categorie;texte
   A.5.1;<intitulé de votre copie>;<catégorie>;<texte de votre copie, facultatif>
   ```

   93 mesures attendues (A.5.1 à A.8.34). Laissez `texte` vide si vous ne voulez embarquer que les intitulés.

2. Déposez-le dans **`data/private/`** (exclu de Git : il ne doit **jamais** être commité ni partagé à des personnes sans licence).

3. Importez pour votre organisation :

   ```bash
   docker compose exec backend python manage.py importer_referentiel iso27001 --organisation mon-organisation --fichier /data/private/iso27001.csv
   ```

## Nouvelle version d'un référentiel

Quand une nouvelle version est importée et reliée à l'ancienne, la Bibliothèque affiche « Nouvelle version disponible ». Les projets restent sur la version choisie à leur création (pas de migration automatique des évaluations à ce jour).

## Correspondances entre référentiels

Dans la **Bibliothèque**, la fiche d'une mesure permet de la relier à une mesure d'un autre référentiel (équivalente, partielle, « inclut »), avec sa source. Ces correspondances sont **propres à votre organisation** et tracées au journal. Elles documentent qu'une même preuve peut couvrir plusieurs exigences.

## Ajouter un référentiel

C'est un développement : une classe `Importeur` dans `backend/apps/referentiels/importeurs/`. Voir [développement](13-developpement.md#ajouter-un-référentiel).
