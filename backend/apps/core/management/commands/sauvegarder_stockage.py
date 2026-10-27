"""Copie tous les fichiers du bucket (dernière version de chaque objet) dans un dossier, avec un inventaire
des empreintes SHA-256 : la restauration vérifie que rien n'a été altéré entre-temps."""

import hashlib
import json
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.stockage import client_s3

INVENTAIRE = "inventaire.json"


def chemin_sur(racine: Path, cle: str) -> Path:
    """Refuse toute clé qui sortirait du dossier (« .. », chemin absolu)."""
    morceaux = PurePosixPath(cle).parts
    if not morceaux or cle.startswith("/") or ".." in morceaux:
        raise CommandError(f"Clé d'objet refusée : {cle!r}")
    return racine.joinpath(*morceaux)


def sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


class Command(BaseCommand):
    help = "Sauvegarde les fichiers du stockage S3 dans un dossier (inventaire SHA-256 inclus)."

    def add_arguments(self, parser):
        parser.add_argument("dossier", help="Dossier de destination (créé ; doit être vide).")

    def handle(self, dossier, **options):
        racine = Path(dossier)
        if racine.exists() and any(racine.iterdir()):
            raise CommandError(f"{racine} n'est pas vide.")
        (racine / "objets").mkdir(parents=True, exist_ok=True)
        client, bucket = client_s3(), settings.AWS_STORAGE_BUCKET_NAME
        inventaire = []
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            for objet in page.get("Contents", []):
                cible = chemin_sur(racine / "objets", objet["Key"])
                cible.parent.mkdir(parents=True, exist_ok=True)
                client.download_file(bucket, objet["Key"], str(cible))
                inventaire.append({"cle": objet["Key"], "taille": cible.stat().st_size, "sha256": sha256(cible)})
        (racine / INVENTAIRE).write_text(json.dumps(inventaire, ensure_ascii=False, indent=1))
        self.stdout.write(self.style.SUCCESS(f"{len(inventaire)} fichier(s) sauvegardé(s) dans {racine}."))
