"""Guide d'hygiène informatique de l'ANSSI (42 mesures, 2017).

Les intitulés viennent du tableau « Outil de suivi » en annexe (structure stable).
Le niveau (standard / renforcé) et le texte viennent de la page de chaque mesure dans le corps."""

import re
import unicodedata

from pypdf import PdfReader

from apps.referentiels.models import Licence

from .base import ErreurImport, Importeur, MesureImportee

NB_MESURES = 42
RE_CHAPITRE = re.compile(r"^([IVX]+) - (.+?)(?:\s+sTANDARD\s+RENFOR\s*cé)?$")
RE_MESURE = re.compile(r"^(\d{1,2})(?:\s+(.*))?$")
RE_STANDARD = re.compile(r"/\s*sTANDARD")
RE_RENFORCE = re.compile(r"/\s*RENFOR\s*cé")


def normaliser(texte):
    """Lettres et chiffres seulement : insensible aux césures, espaces et accents de l'extraction PDF."""
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", texte)


class HygieneAnssi(Importeur):
    code = "hygiene-anssi"
    nom = "Guide d'hygiène informatique (ANSSI)"
    version = "2.0"  # septembre 2017
    editeur = "ANSSI"
    licence = Licence.LICENCE_OUVERTE
    url = "https://messervices.cyber.gouv.fr/documents-guides/guide_hygiene_informatique_anssi.pdf"
    url_reference = "https://messervices.cyber.gouv.fr/guides/guide-dhygiene-informatique"
    nom_fichier = "guide_hygiene_informatique_anssi.pdf"

    def lire(self, chemin):
        pages = [p.extract_text() or "" for p in PdfReader(chemin).pages]
        debut_annexe = next(
            (i for i, p in enumerate(pages) if "OuTIl dE SuIVI" in p and re.search(r"^I - Sensibiliser", p, re.M)), None
        )
        if debut_annexe is None:
            raise ErreurImport("Tableau « Outil de suivi » introuvable : version du guide différente ?")
        mesures = self._lire_annexe(pages[debut_annexe:])
        self._completer_depuis_le_corps(mesures, pages[:debut_annexe])
        return mesures

    def _lire_annexe(self, pages):
        mesures, chapitre, courante, fini = [], "", None, False
        for page in pages:
            if fini:
                break
            for i, ligne in enumerate(page.splitlines()):
                ligne = ligne.strip()
                if not ligne or (i == 0 and ligne.isdigit()) or ligne.startswith("OuTIl") or RE_STANDARD.sub("", ligne) == "":
                    continue
                if re.fullmatch(r"sTANDARD\s+RENFOR\s*cé", ligne):
                    continue
                if ligne.lower().startswith("bibliograp"):
                    fini = True
                    break
                if m := RE_CHAPITRE.match(ligne):
                    chapitre = f"{m.group(1)} - {m.group(2).strip().capitalize()}"
                    courante = None
                    continue
                m = RE_MESURE.match(ligne)
                if m and int(m.group(1)) == len(mesures) + 1:
                    courante = MesureImportee(identifiant=f"M{int(m.group(1)):02d}", intitule=m.group(2) or "", categorie=chapitre)
                    mesures.append(courante)
                elif courante is not None:
                    courante.intitule = f"{courante.intitule} {ligne}".strip()
        for m in mesures:
            m.intitule = re.sub(r"\s+", " ", m.intitule).strip()
        if len(mesures) != NB_MESURES:
            raise ErreurImport(f"{len(mesures)} mesures lues au lieu de {NB_MESURES}.")
        return mesures

    @staticmethod
    def _porte_le_numero(page, numero):
        """Dans le corps, le numéro de mesure est une ligne isolée suivie du titre (hors en-tête de page)."""
        lignes = [l.strip() for l in page.splitlines()]
        return any(
            l == str(numero) and j + 1 < len(lignes) and lignes[j + 1][:1].isupper()
            for j, l in enumerate(lignes) if j >= 3
        )

    def _completer_depuis_le_corps(self, mesures, pages):
        pages_norm = [normaliser(p) for p in pages]
        depuis = 0
        for numero, mesure in enumerate(mesures, start=1):
            amorce = normaliser(mesure.intitule)[:35]
            index = next((i for i in range(depuis, len(pages)) if self._porte_le_numero(pages[i], numero)), None)
            if index is None:
                index = next((i for i in range(depuis, len(pages)) if amorce in pages_norm[i]), None)
            if index is None:
                raise ErreurImport(f"Page de la mesure {mesure.identifiant} introuvable.")
            depuis = index
            page = pages[index]
            mesure.niveaux = [n for n, rx in (("standard", RE_STANDARD), ("renforcé", RE_RENFORCE)) if rx.search(page)]
            if not mesure.niveaux:
                raise ErreurImport(f"Niveau de la mesure {mesure.identifiant} introuvable.")
            mesure.texte = self._nettoyer(page)

    @staticmethod
    def _nettoyer(page):
        lignes = [
            l for l in page.splitlines()
            if l.strip() and not l.strip().isdigit() and "Guide d’hygiène informatique" not in l
            and not RE_STANDARD.fullmatch(l.strip()) and not RE_RENFORCE.fullmatch(l.strip())
            and not re.fullmatch(r"[IVX]+", l.strip())
        ]
        texte = "\n".join(lignes)
        texte = re.sub(r"-\n(?=\w)", "", texte)  # césures de fin de ligne
        texte = re.sub(r"(?<![.;:!?»])\n(?![ >•])", " ", texte)
        return re.sub(r"[ \t]{2,}", " ", texte).strip()
