"""Prépare le bucket S3 de l'application (idempotent) : création, accès public bloqué, versioning.
Fonctionne avec tout stockage S3-compatible (SeaweedFS en dev, Scaleway en prod)."""

import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée le bucket S3 de SoluGation s'il n'existe pas et active le versioning."

    def add_arguments(self, parser):
        parser.add_argument("--attente", type=int, default=30, help="Secondes d'attente max du stockage au démarrage.")

    def handle(self, attente, **options):
        client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 2}),
        )
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        limite = time.monotonic() + attente
        while True:
            try:
                client.head_bucket(Bucket=bucket)
                self.stdout.write(f"Bucket « {bucket} » présent.")
                break
            except EndpointConnectionError:
                if time.monotonic() > limite:
                    raise CommandError(f"Stockage S3 injoignable : {settings.AWS_S3_ENDPOINT_URL}")
                time.sleep(1)
            except ClientError as e:
                if e.response["Error"]["Code"] not in ("404", "NoSuchBucket", "NotFound"):
                    raise CommandError(f"Accès au bucket refusé : {e}") from e
                client.create_bucket(Bucket=bucket)
                self.stdout.write(self.style.SUCCESS(f"Bucket « {bucket} » créé."))
                break

        # Chaque garde-fou est tenté : un stockage qui ne le gère pas est signalé, sans bloquer le démarrage.
        for nom, appel in (
            ("versioning", lambda: client.put_bucket_versioning(
                Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})),
            ("blocage de l'accès public", lambda: client.put_public_access_block(
                Bucket=bucket, PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True, "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True, "RestrictPublicBuckets": True})),
        ):
            try:
                appel()
                self.stdout.write(f"  {nom} : activé")
            except ClientError as e:
                self.stdout.write(self.style.WARNING(f"  {nom} : non pris en charge par ce stockage ({e.response['Error']['Code']})"))
