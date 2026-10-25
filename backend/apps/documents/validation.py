"""Contrôle des fichiers déposés : liste blanche par signature réelle du contenu, taille max, hash SHA-256.
L'extension et le Content-Type annoncés par le client ne font jamais foi ; l'extension stockée est
celle du type détecté (le nom d'origine n'est conservé qu'en base, le nom S3 est régénéré)."""

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from rest_framework.exceptions import ValidationError

TAILLE_ENTETE = 8192
RATIO_DECOMPRESSION_MAX = 100  # au-delà : archive suspecte (zip bomb)
OOXML = {
    "word/": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xl/": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
ODF = {
    "application/vnd.oasis.opendocument.text": "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet": "application/vnd.oasis.opendocument.spreadsheet",
}


@dataclass
class FichierControle:
    type_mime: str
    extension: str
    taille: int
    sha256: str


def _type_zip(fichier, taille):
    fichier.seek(0)
    try:
        with zipfile.ZipFile(fichier) as z:
            noms = z.namelist()
            if sum(i.file_size for i in z.infolist()) > max(taille, 1) * RATIO_DECOMPRESSION_MAX:
                raise ValidationError("Archive au taux de compression anormal : refusée.")
            if any(n.lower().endswith("vbaproject.bin") or "/macros/" in n.lower() or n.startswith("Basic/") for n in noms):
                raise ValidationError("Document contenant des macros : refusé.")
            if "mimetype" in noms:
                return ODF.get(z.read("mimetype").decode("ascii", "ignore").strip())
            if "[Content_Types].xml" in noms:
                return next((mime for prefixe, mime in OOXML.items() if any(n.startswith(prefixe) for n in noms)), None)
    except zipfile.BadZipFile:
        return None
    return None


def _type_texte(entete, extension):
    if b"\x00" in entete:
        return None
    try:
        texte = entete.decode("utf-8")
    except UnicodeDecodeError:
        try:
            texte = entete[:-4].decode("utf-8")  # caractère multi-octets coupé en fin d'en-tête
        except UnicodeDecodeError:
            return None
    debut = texte.lstrip("﻿ \r\n\t")
    if debut.startswith("<?xml") or (extension in (".xml", ".nessus") and debut.startswith("<")):
        return "application/xml"
    if debut[:15].lower().startswith(("<!doctype html", "<html", "<script", "<svg")):
        return None  # contenu actif : jamais servi depuis le coffre
    return "text/csv" if extension == ".csv" else "text/plain"


def detecter_type(fichier, nom, taille):
    fichier.seek(0)
    entete = fichier.read(TAILLE_ENTETE)
    extension = Path(nom).suffix.lower()
    if entete.startswith(b"%PDF-"):
        return "application/pdf"
    if entete.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if entete.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if entete.startswith(b"PK\x03\x04"):
        return _type_zip(fichier, taille)
    return _type_texte(entete, extension)


def controler(fichier, nom) -> FichierControle:
    taille = fichier.size
    if taille == 0:
        raise ValidationError("Fichier vide.")
    if taille > settings.SOLUGATION_UPLOAD_MAX_OCTETS:
        raise ValidationError(f"Fichier trop volumineux (max {settings.SOLUGATION_UPLOAD_MAX_OCTETS // (1024 * 1024)} Mo).")
    type_mime = detecter_type(fichier, nom, taille)
    autorises = settings.SOLUGATION_UPLOAD_TYPES_AUTORISES
    if type_mime not in autorises:
        raise ValidationError("Type de fichier non autorisé.")
    h = hashlib.sha256()
    fichier.seek(0)
    for bloc in fichier.chunks():
        h.update(bloc)
    fichier.seek(0)
    return FichierControle(type_mime, autorises[type_mime], taille, h.hexdigest())

