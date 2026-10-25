"""ISO/IEC 27001:2022 Annexe A. Norme payante : aucun texte n'est fourni par SoluGation.
Import uniquement depuis la copie licenciée de l'organisation, en CSV sous data/private/ :

    identifiant;intitule;categorie;texte
    A.5.1;<intitulé de votre copie>;<catégorie>;<texte facultatif>

`texte` vide partout = version commerciale (identifiant + intitulé reformulé, texte_embarque = False)."""

import csv
import re

from apps.referentiels.models import Licence

from .base import ErreurImport, Importeur, MesureImportee

COLONNES = {"identifiant", "intitule", "categorie"}
RE_IDENTIFIANT = re.compile(r"^A\.[5-8]\.\d{1,2}$")
NB_MESURES = 93


class Iso27001(Importeur):
    code = "iso27001"
    nom = "ISO/IEC 27001 — Annexe A"
    version = "2022"
    editeur = "ISO/IEC"
    licence = Licence.PROPRIETAIRE
    url_reference = "https://www.iso.org/standard/27001"
    prive = True

    def __init__(self, fichier=None, organisation=None):
        if organisation is None:
            raise ErreurImport("Copie licenciée : préciser --organisation (le texte ne va pas dans la bibliothèque commune).")
        super().__init__(fichier, organisation)

    def lire(self, chemin):
        contenu = chemin.read_text(encoding="utf-8-sig")
        dialecte = csv.Sniffer().sniff(contenu.splitlines()[0], delimiters=";,")
        lignes = list(csv.DictReader(contenu.splitlines(), dialect=dialecte))
        if not lignes or not COLONNES <= set(lignes[0]):
            raise ErreurImport(f"Colonnes attendues : {', '.join(sorted(COLONNES))} (+ texte facultatif).")
        mesures = []
        for n, ligne in enumerate(lignes, start=2):
            identifiant = ligne["identifiant"].strip()
            if not RE_IDENTIFIANT.match(identifiant):
                raise ErreurImport(f"Ligne {n} : identifiant inattendu « {identifiant} ».")
            texte = (ligne.get("texte") or "").strip() or None
            mesures.append(
                MesureImportee(identifiant, ligne["intitule"].strip(), ligne["categorie"].strip(), texte)
            )
        if len(mesures) != NB_MESURES:
            raise ErreurImport(f"{len(mesures)} mesures lues, l'Annexe A 2022 en compte {NB_MESURES}.")
        self.texte_embarque = any(m.texte for m in mesures)
        return mesures
