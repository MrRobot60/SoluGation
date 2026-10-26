"""Extraction locale du texte des documents déposés (aucun service externe). Le texte est découpé en pages
quand le format en a (PDF), en blocs sinon, pour que les citations de l'IA puissent être localisées et vérifiées.
Les images et les PDF scannés (sans couche texte) ne sont pas analysables : pas d'OCR en V1."""

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field

from defusedxml import ElementTree
from pypdf import PdfReader

TEXTE_MAX = 400_000  # caractères analysés par document, au-delà : tronqué (et signalé)
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
ODF_TEXTE = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
ODF_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"


class NonAnalysable(Exception):
    pass


@dataclass
class TexteExtrait:
    pages: list[tuple[int | None, str]] = field(default_factory=list)  # (n° de page ou None, texte)
    tronque: bool = False

    @property
    def longueur(self):
        return sum(len(t) for _, t in self.pages)


def _nettoyer(texte):
    return re.sub(r"[ \t ]+", " ", re.sub(r"\n{3,}", "\n\n", texte.replace("\r", ""))).strip()


def _pdf(flux):
    lecteur = PdfReader(flux)
    if lecteur.is_encrypted:
        raise NonAnalysable("PDF chiffré.")
    return [(i, lecteur.pages[i - 1].extract_text() or "") for i in range(1, len(lecteur.pages) + 1)]


def _paragraphes_xml(donnees, balise_paragraphe, balise_texte=None):
    racine = ElementTree.fromstring(donnees)
    paragraphes = []
    for p in racine.iter(balise_paragraphe):
        noeuds = p.iter(balise_texte) if balise_texte else [p]
        paragraphes.append("".join("".join(n.itertext()) for n in noeuds))
    return "\n".join(x for x in paragraphes if x.strip())


def _docx(flux):
    with zipfile.ZipFile(flux) as z:
        return [(None, _paragraphes_xml(z.read("word/document.xml"), f"{W}p", f"{W}t"))]


def _odt(flux):
    with zipfile.ZipFile(flux) as z:
        racine = ElementTree.fromstring(z.read("content.xml"))
    blocs = [("".join(n.itertext())) for n in racine.iter() if n.tag in (f"{ODF_TEXTE}p", f"{ODF_TEXTE}h")]
    return [(None, "\n".join(b for b in blocs if b.strip()))]


def _ods(flux):
    with zipfile.ZipFile(flux) as z:
        racine = ElementTree.fromstring(z.read("content.xml"))
    lignes = [" | ".join("".join(c.itertext()) for c in r.iter(f"{ODF_TABLE}table-cell")) for r in racine.iter(f"{ODF_TABLE}table-row")]
    return [(None, "\n".join(l for l in lignes if l.strip(" |")))]


def _xlsx(flux):
    with zipfile.ZipFile(flux) as z:
        partagees = []
        if "xl/sharedStrings.xml" in z.namelist():
            partagees = ["".join(si.itertext()) for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{S}si")]
        feuilles = sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        lignes = []
        for nom in feuilles:
            for ligne in ElementTree.fromstring(z.read(nom)).iter(f"{S}row"):
                cellules = []
                for c in ligne.iter(f"{S}c"):
                    v = c.find(f"{S}v")
                    if c.get("t") == "s" and v is not None and v.text and v.text.isdigit() and int(v.text) < len(partagees):
                        cellules.append(partagees[int(v.text)])
                    elif c.get("t") == "inlineStr":
                        cellules.append("".join(c.itertext()))
                    elif v is not None and v.text:
                        cellules.append(v.text)
                if any(x.strip() for x in cellules):
                    lignes.append(" | ".join(cellules))
    return [(None, "\n".join(lignes))]


def _texte(flux):
    brut = flux.read()
    for codage in ("utf-8-sig", "cp1252"):
        try:
            return [(None, brut.decode(codage))]
        except UnicodeDecodeError:
            continue
    raise NonAnalysable("Encodage du texte non reconnu.")


def _csv(flux):
    (_, texte), = _texte(flux)
    return [(None, "\n".join(" | ".join(l) for l in csv.reader(io.StringIO(texte))))]


EXTRACTEURS = {
    "application/pdf": _pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _docx,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": _xlsx,
    "application/vnd.oasis.opendocument.text": _odt,
    "application/vnd.oasis.opendocument.spreadsheet": _ods,
    "text/plain": _texte,
    "text/csv": _csv,
    "application/xml": _texte,
}


def extraire(document) -> TexteExtrait:
    extracteur = EXTRACTEURS.get(document.type_mime)
    if extracteur is None:
        raise NonAnalysable("Format non analysable (image) : pas de reconnaissance de caractères en V1.")
    with document.fichier.open("rb") as f:
        flux = io.BytesIO(f.read())
    try:
        pages = extracteur(flux)
    except NonAnalysable:
        raise
    except Exception:
        raise NonAnalysable("Lecture du document impossible (fichier corrompu ou format inattendu).") from None
    resultat, total = TexteExtrait(), 0
    for numero, texte in pages:
        texte = _nettoyer(texte)
        if not texte:
            continue
        if total + len(texte) > TEXTE_MAX:
            texte, resultat.tronque = texte[: TEXTE_MAX - total], True
        resultat.pages.append((numero, texte))
        total += len(texte)
        if resultat.tronque:
            break
    if total < 50:
        raise NonAnalysable("Aucun texte exploitable (document scanné ou vide) : pas de reconnaissance de caractères en V1.")
    return resultat
