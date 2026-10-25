"""Socle des imports de référentiels : téléchargement reproductible, empreinte, upsert idempotent."""

import hashlib
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.referentiels.models import Mesure, Referentiel


class ErreurImport(Exception):
    pass


@dataclass
class MesureImportee:
    identifiant: str
    intitule: str
    categorie: str = ""
    texte: str | None = None
    niveaux: list[str] = field(default_factory=list)
    parent: str | None = None  # identifiant de la mesure parente


@dataclass
class Resultat:
    referentiel: Referentiel
    crees: int
    mis_a_jour: int


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


class Importeur:
    """Une sous-classe par référentiel. `url` vide = pas de téléchargement automatique,
    le fichier doit être fourni (`--fichier`)."""

    code: str
    nom: str
    version: str
    editeur: str
    licence: str
    url: str = ""
    url_reference: str = ""  # page officielle affichée dans l'appli
    nom_fichier: str = ""
    texte_embarque = True
    prive = False  # copie licenciée : fichier obligatoirement sous data/private/

    def __init__(self, fichier: Path | None = None, organisation=None):
        self.fichier = Path(fichier) if fichier else None
        self.organisation = organisation

    # --- source -----------------------------------------------------------------------

    def dossier_sources(self) -> Path:
        return settings.SOLUGATION_DATA_DIR / "sources" / self.code / self.version

    def obtenir_fichier(self) -> Path:
        if self.fichier:
            chemin = self.fichier.resolve()
            if not chemin.is_file():
                raise ErreurImport(f"Fichier introuvable : {chemin}")
            if self.prive and not chemin.is_relative_to((settings.SOLUGATION_DATA_DIR / "private").resolve()):
                raise ErreurImport("Une copie licenciée doit être placée sous data/private/ (ignoré par git).")
            return chemin
        if not self.url:
            raise ErreurImport(f"Pas de téléchargement automatique pour {self.code} : fournir --fichier.")
        chemin = self.dossier_sources() / self.nom_fichier
        if not chemin.exists():
            chemin.parent.mkdir(parents=True, exist_ok=True)
            requete = urllib.request.Request(self.url, headers={"User-Agent": "SoluGation-import/1.0"})
            with urllib.request.urlopen(requete, timeout=60) as reponse, open(chemin.with_suffix(".part"), "wb") as f:
                f.write(reponse.read())
            chemin.with_suffix(".part").rename(chemin)
        return chemin

    def lire(self, chemin: Path) -> list[MesureImportee]:
        raise NotImplementedError

    # --- écriture ---------------------------------------------------------------------

    @transaction.atomic
    def importer(self) -> Resultat:
        chemin = self.obtenir_fichier()
        mesures = self.lire(chemin)
        identifiants = [m.identifiant for m in mesures]
        if not mesures or len(set(identifiants)) != len(identifiants):
            raise ErreurImport("Source vide ou identifiants en double : format inattendu ?")

        referentiel, _ = Referentiel.objects.update_or_create(
            organisation=self.organisation,
            code=self.code,
            version=self.version,
            defaults={
                "nom": self.nom,
                "editeur": self.editeur,
                "licence": self.licence,
                "url_source": self.url or self.url_reference,
                "texte_embarque": self.texte_embarque,
                "empreinte_source": sha256_fichier(chemin),
                "date_import": timezone.now(),
                "actif": True,
            },
        )
        existantes = {m.identifiant: m for m in referentiel.mesures.all()}
        crees = mis_a_jour = 0
        objets = {}
        for ordre, m in enumerate(mesures):
            valeurs = {
                "intitule": m.intitule[:500],
                "categorie": m.categorie[:200],
                "texte_officiel": m.texte if self.texte_embarque else None,
                "niveaux": m.niveaux,
                "ordre": ordre,
            }
            obj = existantes.get(m.identifiant)
            if obj is None:
                obj = Mesure.objects.create(referentiel=referentiel, identifiant=m.identifiant, **valeurs)
                crees += 1
            elif any(getattr(obj, k) != v for k, v in valeurs.items()):
                for k, v in valeurs.items():
                    setattr(obj, k, v)
                obj.save()
                mis_a_jour += 1
            objets[m.identifiant] = obj
        for m in mesures:
            parent = objets.get(m.parent) if m.parent else None
            if objets[m.identifiant].parent_id != getattr(parent, "id", None):
                objets[m.identifiant].parent = parent
                objets[m.identifiant].save(update_fields=["parent"])

        # Alerte de mise à jour : les anciennes versions pointent vers celle-ci.
        Referentiel.objects.filter(organisation=self.organisation, code=self.code).exclude(pk=referentiel.pk).update(
            remplace_par=referentiel
        )
        return Resultat(referentiel, crees, mis_a_jour)
