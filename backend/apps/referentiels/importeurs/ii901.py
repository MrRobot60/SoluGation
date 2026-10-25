"""Instruction interministérielle n° 901/SGDSN/ANSSI du 28 janvier 2015 (NOR PRMD1503279J).

Source : circulaire publiée sur Légifrance (cir_39217.pdf), document scanné puis OCRisé. Les mesures
sont les règles de l'annexe 1 (`CODE : intitulé. texte`), regroupées par objectif (1 à 34).
Les numéros d'objectifs étant abîmés par l'OCR, ils sont recomptés dans l'ordre du document (34 objectifs, 178 règles).
Le texte des règles reste celui de l'OCR : à relire avant tout usage contractuel."""

import re

from pypdf import PdfReader

from apps.referentiels.models import Licence

from .base import ErreurImport, Importeur, MesureImportee

NB_OBJECTIFS = 34
NB_REGLES = 178

# Confusions OCR constatées sur les codes (O/D, Y/V), chacune confirmée par l'intitulé de la règle.
# Pas de remplacement global : Y est légitime dans PHY ou DYN.
CORRECTIONS_CODES = (
    (re.compile(r"^POT-"), "PDT-"),
    (re.compile(r"^DEY-"), "DEV-"),
    (re.compile(r"-YERIF$"), "-VERIF"),
    (re.compile(r"-AMOY$"), "-AMOV"),
    (re.compile(r"-SERY$"), "-SERV"),
    (re.compile(r"-OESACTIV$"), "-DESACTIV"),
)
# Segments du code : l'OCR insère parfois des espaces (« DEY -FIL T -APPL »).
RE_REGLE = re.compile(r"^\s*([A-Z]{2,6}(?:\s*-\s*[A-Z0-9](?:[A-Z0-9 ]{0,24}[A-Z0-9])?)+)\s*:\s*(.*)$")
RE_OBJECTIF = re.compile(r"^\s*Obje\S{0,6}.{0,8}:\s*$")
RE_BRUIT = re.compile(r"^\s*(<<PAGE>>|\d{1,2}|\d+ Ces règles sont adaptées.*)\s*$")


def corriger_code(code):
    code = re.sub(r"\s+", "", code)
    for motif, remplacement in CORRECTIONS_CODES:
        code = motif.sub(remplacement, code)
    return code


def corriger_texte(texte):
    texte = re.sub(r"(?<![\w'])([A-ZÉ]) (?=[a-zéè]{2,})", r"\1", texte)  # « G érer » lu pour « Gérer »
    texte = re.sub(r"(?<=\s)1\s?'(?=\w)", "l'", texte)  # « 1'entité » lu pour « l'entité »
    texte = re.sub(r"\s+'\s?", "'", texte)
    texte = re.sub(r"\s+([,.;:])", r"\1", texte)
    return re.sub(r"\s{2,}", " ", texte).strip()


class Ii901(Importeur):
    code = "ii901"
    nom = "II 901/SGDSN/ANSSI — Protection des systèmes d'information sensibles"
    version = "2015"
    editeur = "SGDSN / ANSSI"
    licence = Licence.LIBRE
    url_reference = "https://www.legifrance.gouv.fr/circulaire/id/39217"
    nom_fichier = "cir_39217.pdf"

    nb_objectifs, nb_regles = NB_OBJECTIFS, NB_REGLES

    def lire(self, chemin):
        return self.analyser("\n<<PAGE>>\n".join(p.extract_text() or "" for p in PdfReader(chemin).pages))

    def analyser(self, texte):
        debut = texte.find("Annexe 1 -Règles")
        fin = texte.find("Annexe 2", debut)
        if debut < 0 or fin < 0:
            raise ErreurImport("Annexe 1 introuvable : document différent de la circulaire attendue ?")
        lignes = [l.strip() for l in texte[debut:fin].splitlines()[1:] if l.strip() and not RE_BRUIT.match(l)]

        mesures, objectif, num_objectif, courante = [], "", 0, None
        en_attente = []  # lignes courtes après une fin de phrase : intertitre probable
        lire_objectif = False
        for ligne in lignes:
            if RE_OBJECTIF.match(ligne):
                num_objectif += 1
                objectif, lire_objectif, en_attente = f"Objectif {num_objectif} —", True, []
                courante = None
                continue
            regle = RE_REGLE.match(ligne)
            if lire_objectif and not regle and (objectif.endswith("—") or ligne[:1].islower()):
                objectif += " " + ligne  # libellé de l'objectif, continué tant que la ligne suit la phrase
                continue
            lire_objectif = False
            if regle:
                en_attente = []
                courante = MesureImportee(
                    identifiant=corriger_code(regle.group(1)), intitule="", categorie=corriger_texte(objectif),
                    texte=regle.group(2),
                )
                mesures.append(courante)
            elif courante is not None:
                fin_de_phrase = courante.texte.rstrip().endswith((".", ";", ":")) or en_attente
                if fin_de_phrase and not ligne.startswith("-") and not ligne.endswith((".", ";", ",")) and len(ligne) < 90:
                    en_attente.append(ligne)
                else:
                    courante.texte += " " + " ".join(en_attente + [ligne])
                    en_attente = []
        for m in mesures:
            m.texte = corriger_texte(m.texte)
            titre, _, _ = m.texte.partition(". ")
            m.intitule = titre[:1].upper() + titre[1:].rstrip(".")
            m.texte = f"{m.identifiant} : {m.texte}"

        if num_objectif != self.nb_objectifs or len(mesures) != self.nb_regles:
            raise ErreurImport(
                f"{num_objectif} objectifs / {len(mesures)} règles lus, attendu {self.nb_objectifs} / {self.nb_regles}."
            )
        return mesures
