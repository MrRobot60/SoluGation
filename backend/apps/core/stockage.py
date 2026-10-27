"""Client S3 de l'application (tout stockage compatible S3 : SeaweedFS intégré, Scaleway, OVHcloud…)."""

import boto3
from botocore.config import Config
from django.conf import settings


def client_s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 2}),
    )
