"""Référentiel général de sécurité v2.0 (arrêté du 13 juin 2014), ANSSI.

Mesures retenues, celles qui s'appliquent au système à homologuer :
- corps du texte : démarche obligatoire (§2.1 à 2.5) et recommandations d'application (§7.1 à 7.13) ;
- annexes B1 (mécanismes cryptographiques), B2 (gestion des clés), B3 (authentification) :
  règles (obligatoires) et recommandations, avec leurs identifiants officiels.
Les annexes A1 à A5 (prestataires de certification et d'horodatage) et C (prestataires d'audit)
visent des prestataires, pas le système : elles ne sont pas importées comme mesures.

Source : téléchargement manuel depuis cyber.gouv.fr (protégé contre les accès automatisés)."""

import re
import unicodedata

from pypdf import PdfReader

from apps.referentiels.models import Licence

from .base import ErreurImport, Importeur, MesureImportee

CORPS = "RGS_v-2-00_Corps_du_texte.pdf"
ANNEXES_B = {
    "B1": ("RGS_v-2-0_B1.pdf", "Annexe B1 — Mécanismes cryptographiques", 64),
    "B2": ("RGS_v-2-0_B2.pdf", "Annexe B2 — Gestion des clés cryptographiques", 48),
    "B3": ("RGS_v-2-0_B3.pdf", "Annexe B3 — Mécanismes d'authentification", 25),
}
SECTIONS_CORPS = {"2": (5, "obligatoire"), "7": (13, "recommandé")}

RE_REGLE = re.compile(r"^\s*((?:Règle|Recom)[\wÀ-ÿ-]*?)\s*\.\s+(.*)$")
RE_TITRE = re.compile(r"^\s*(\d+(?:\.\d+){1,3})\s+([A-ZÉÀ][^.]{3,130}?)\s*$")
RE_FIN_REGLE = re.compile(r"^\s*(Justifications?\s*:|Remarques?\s*:|Note\s*:)")
RE_BRUIT = re.compile(
    r"^\s*(<<PAGE>>|\d{1,3}|Annexe B\d au R[ée]f[ée]rentiel.*|Annexe B\d au RGS.*|Version Date Crit[eè]re.*"
    r"|V?\d\.\d+\s+(?:\d{1,2} \w+ \d{4}|\d{2}/\d{2}/\d{4})\s+PUBLIC.*|Version du RGS Date.*|2\.0 13 juin 2014 PUBLIC.*"
    r"|Référentiel général de sécurité\s*)\s*$"
)


def lignes_pdf(chemin):
    texte = "\n".join(p.extract_text() or "" for p in PdfReader(chemin).pages)
    texte = unicodedata.normalize("NFKC", texte)
    return [l.rstrip() for l in texte.splitlines() if l.strip() and not RE_BRUIT.match(l)]


def nettoyer(texte):
    texte = re.sub(r"(\w)-\s+(?=[a-zéèà])", r"\1", texte)  # césures de fin de ligne
    texte = re.sub(r"\s+([,.;:)])", r"\1", texte)
    return re.sub(r"\s{2,}", " ", texte).strip()


def premiere_phrase(texte, n=500):
    phrase = re.split(r"(?<=[.;])\s", texte, maxsplit=1)[0]
    return phrase if len(phrase) <= n else phrase[: n - 1] + "…"


class Rgs(Importeur):
    code = "rgs"
    nom = "Référentiel général de sécurité (RGS)"
    version = "2.0"
    editeur = "ANSSI"
    licence = Licence.LIBRE
    url_reference = "https://cyber.gouv.fr/le-referentiel-general-de-securite-rgs"
    fichiers_attendus = (CORPS,) + tuple(f for f, _, _ in ANNEXES_B.values())

    def lire(self, chemin):
        mesures = self._lire_corps(chemin / CORPS)
        for annexe, (fichier, titre, attendu) in ANNEXES_B.items():
            lues = self._lire_annexe(chemin / fichier, annexe, titre)
            if len(lues) != attendu:
                raise ErreurImport(f"{annexe} : {len(lues)} règles/recommandations lues au lieu de {attendu}.")
            mesures += lues
        return mesures

    def _lire_corps(self, fichier):
        lignes = lignes_pdf(fichier)
        # Le sommaire reprend les titres : on démarre au premier « Chapitre 2. » suivi de texte (corps).
        debut = max(i for i, l in enumerate(lignes) if l.strip().startswith("Chapitre 2."))
        mesures, chapitre, courante, titre_ouvert = [], "", None, False
        for ligne in lignes[debut:]:
            if m := re.match(r"^\s*Chapitre (\d+)\.\s*(.*)$", ligne):
                chapitre_num, courante = m.group(1), None
                chapitre = f"Chapitre {chapitre_num} — {m.group(2).strip()}"
                continue
            m = RE_TITRE.match(ligne)
            if m and m.group(1).split(".")[0] in SECTIONS_CORPS and m.group(1).count(".") == 1:
                courante = MesureImportee(
                    identifiant=f"§{m.group(1)}", intitule=m.group(2).strip(), categorie=chapitre, texte="",
                    niveaux=[SECTIONS_CORPS[m.group(1).split(".")[0]][1]],
                )
                mesures.append(courante)
                titre_ouvert = True
                continue
            if courante is None or chapitre_num not in SECTIONS_CORPS:
                continue
            # Titre sur deux lignes, sauf sous-point « a Organiser… » qui ouvre le texte.
            if titre_ouvert and ligne.strip()[:1].islower() and not re.match(r"^\s*[a-z] [A-ZÉ]", ligne):
                courante.intitule += " " + ligne.strip()
                continue
            titre_ouvert = False
            courante.texte += " " + ligne
        for m in mesures:
            m.intitule, m.texte = nettoyer(m.intitule), nettoyer(m.texte)
        for chap, (nb, _) in SECTIONS_CORPS.items():
            lues = [m for m in mesures if m.identifiant.startswith(f"§{chap}.")]
            if len(lues) != nb:
                raise ErreurImport(f"Corps du texte, chapitre {chap} : {len(lues)} sections lues au lieu de {nb}.")
        return mesures

    def _lire_annexe(self, fichier, annexe, titre_annexe):
        return self.analyser_annexe(lignes_pdf(fichier), annexe, titre_annexe)

    @staticmethod
    def analyser_annexe(lignes, annexe, titre_annexe):
        mesures, section, courante, vus = [], "", None, set()
        for ligne in lignes:
            if "...." in ligne:  # sommaire et index
                continue
            if m := RE_TITRE.match(ligne):
                section, courante = f"{m.group(1)} {m.group(2).strip()}", None
                continue
            if m := RE_REGLE.match(ligne):
                ident = m.group(1)
                if ident in vus:  # identifiant réutilisé dans le document officiel (B2)
                    ident += "-bis"
                vus.add(ident)
                courante = MesureImportee(
                    identifiant=f"{annexe}-{ident}", intitule="",
                    categorie=f"{titre_annexe} › {section}" if section else titre_annexe,
                    texte=m.group(2), niveaux=["obligatoire" if ident.startswith("Règle") else "recommandé"],
                )
                mesures.append(courante)
                continue
            if courante is None:
                continue
            if RE_FIN_REGLE.match(ligne):
                courante = None
                continue
            courante.texte += " " + ligne
        for m in mesures:
            m.texte = nettoyer(m.texte)
            m.intitule = premiere_phrase(m.texte)
        return mesures
