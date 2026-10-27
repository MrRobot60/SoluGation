"""Remet dans le bucket les fichiers d'une sauvegarde (`sauvegarder_stockage`), après contrôle des empreintes."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.stockage import client_s3

from .sauvegarder_stockage import INVENTAIRE, chemin_sur, sha256


class Command(BaseCommand):
    help = "Restaure les fichiers d'une sauvegarde dans le stockage S3 (empreintes vérifiées avant tout envoi)."

    def add_arguments(self, parser):
        parser.add_argument("dossier", help="Dossier produit par sauvegarder_stockage.")

    def handle(self, dossier, **options):
        racine = Path(dossier)
        try:
            inventaire = json.loads((racine / INVENTAIRE).read_text())
        except FileNotFoundError:
            raise CommandError(f"Pas d'{INVENTAIRE} dans {racine} : ce n'est pas une sauvegarde de fichiers.")
        # Tout est vérifié avant d'envoyer quoi que ce soit : pas de restauration partielle d'une sauvegarde altérée.
        fichiers = []
        for entree in inventaire:
            chemin = chemin_sur(racine / "objets", entree["cle"])
            if not chemin.is_file() or sha256(chemin) != entree["sha256"]:
                raise CommandError(f"Fichier absent ou altéré dans la sauvegarde : {entree['cle']}")
            fichiers.append((entree["cle"], chemin))
        client, bucket = client_s3(), settings.AWS_STORAGE_BUCKET_NAME
        extra = getattr(settings, "AWS_S3_OBJECT_PARAMETERS", None)
        for cle, chemin in fichiers:
            client.upload_file(str(chemin), bucket, cle, ExtraArgs=extra)
        self.stdout.write(self.style.SUCCESS(f"{len(fichiers)} fichier(s) restauré(s)."))
