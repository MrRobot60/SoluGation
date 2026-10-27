"""Contrôles de configuration de production (`manage.py check --deploy`, lancé à chaque démarrage en production) :
une valeur d'exemple ou un réglage dangereux empêche le démarrage plutôt que de passer inaperçu."""

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register

EXEMPLE = "a-remplacer"


@register(Tags.security, deploy=True)
def configuration_production(app_configs, **kwargs):
    problemes = []
    secrets = {
        "DJANGO_SECRET_KEY": settings.SECRET_KEY,
        "POSTGRES_PASSWORD / DATABASE_URL": settings.DATABASES["default"].get("PASSWORD", ""),
        "S3_SECRET_KEY": settings.AWS_SECRET_ACCESS_KEY,
    }
    for nom, valeur in secrets.items():
        if not valeur or EXEMPLE in valeur:
            problemes.append(Error(f"{nom} a encore sa valeur d'exemple.", hint="Générez une valeur aléatoire (docs/02-installation.md).",
                                   id="solugation.E001"))
    if len(settings.SECRET_KEY) < 40:
        problemes.append(Error("DJANGO_SECRET_KEY est trop courte (40 caractères minimum).", id="solugation.E002"))
    if not settings.ALLOWED_HOSTS:
        problemes.append(Error("Aucun nom d'hôte autorisé.", hint="Renseignez SOLUGATION_DOMAINE.", id="solugation.E003"))
    if not settings.FRONTEND_URL.startswith("https://"):
        problemes.append(Warning("FRONTEND_URL n'est pas en HTTPS : les liens des mails seront en clair.", id="solugation.W001"))
    if settings.EMAIL_BACKEND.endswith("console.EmailBackend"):
        problemes.append(Warning("Aucun serveur SMTP (EMAIL_HOST) : aucun mail ne partira.", id="solugation.W002"))
    if not getattr(settings, "AWS_S3_OBJECT_PARAMETERS", {}).get("ServerSideEncryption"):
        problemes.append(Warning("Chiffrement au repos du stockage non demandé (S3_SSE).",
                                 hint="AES256 chez un hébergeur S3 ; avec le stockage intégré, chiffrez le disque du serveur.",
                                 id="solugation.W003"))
    if settings.IA_EXECUTION != "taches":
        problemes.append(Warning("Analyses IA exécutées dans le serveur web (IA_EXECUTION=fil) : perdues à son redémarrage.",
                                 id="solugation.W004"))
    return problemes
