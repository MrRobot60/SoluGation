"""Paramètres Django de SoluGation. Toute valeur sensible vient de l'environnement (.env)."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    S3_USE_SSL=(bool, True),
    S3_SSE=(str, ""),
    UPLOAD_MAX_MO=(int, 50),
)
# Les variables déjà présentes dans l'environnement priment sur le fichier .env.
if (BASE_DIR.parent / ".env").exists():
    environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
# Derrière le proxy de production uniquement : l'adresse du client est lue dans X-Forwarded-For.
SOLUGATION_PROXY_DE_CONFIANCE = env.bool("SOLUGATION_PROXY_DE_CONFIANCE", default=False)
# Nombre de proxys devant le serveur : 1 (Caddy seul), 2 (répartiteur de charge ou tunnel, puis Caddy).
SOLUGATION_NB_PROXYS = env.int("SOLUGATION_NB_PROXYS", default=1)
# Production : le nom de domaine public suffit, les listes s'en déduisent (surchargeables).
SOLUGATION_DOMAINE = env("SOLUGATION_DOMAINE", default="")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS") or ([SOLUGATION_DOMAINE] if SOLUGATION_DOMAINE else [])
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS") or ([f"https://{SOLUGATION_DOMAINE}"] if SOLUGATION_DOMAINE else [])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "storages",
    # Applications SoluGation
    "apps.core",
    "apps.comptes",
    "apps.referentiels",
    "apps.projets",
    "apps.documents",
    "apps.ai",
    "apps.suivi",
    "apps.risques",
    "apps.ebios",
    "apps.rapports",
    "apps.scans",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.AdresseClientMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # fichiers statiques de l'admin et de l'API en production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.comptes.middleware.DoubleAuthMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

AUTH_USER_MODEL = "comptes.Utilisateur"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Liens d'invitation et de réinitialisation (apps/comptes/mots_de_passe.py) : borne haute commune (7 jours) ;
# la réinitialisation est limitée à 1 heure par son propre générateur.
PASSWORD_RESET_TIMEOUT = 7 * 24 * 60 * 60
MAILS_COMPTES_SYNCHRONES = env.bool("MAILS_COMPTES_SYNCHRONES", default=False)  # tests uniquement

# Double authentification (application TOTP) : desactivee | facultative (défaut) | administrateurs | tous.
# L'écran Administration (administrateur de l'installation) prime sur cette valeur.
DOUBLE_AUTH_POLITIQUE = env("DOUBLE_AUTH_POLITIQUE", default="facultative")
# Clé Fernet des secrets de double authentification ; vide : dérivée de DJANGO_SECRET_KEY.
SOLUGATION_CLE_CHIFFREMENT = env("SOLUGATION_CLE_CHIFFREMENT", default="")

# Cache partagé entre les processus du serveur (limites de tentatives de connexion, de demandes de lien…).
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "solugation_cache"}}

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
if not STATIC_ROOT.is_dir():  # dev et tests : pas de fichiers compilés (collectstatic se fait dans l'image)
    MIDDLEWARE.remove("whitenoise.middleware.WhiteNoiseMiddleware")

# Stockage S3-compatible (SeaweedFS en local, Scaleway en prod). Un préfixe par organisation,
# voir apps.core.models.chemin_fichier.
AWS_ACCESS_KEY_ID = env("S3_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = env("S3_SECRET_KEY")
AWS_STORAGE_BUCKET_NAME = env("S3_BUCKET")
AWS_S3_ENDPOINT_URL = env("S3_ENDPOINT_URL")
AWS_S3_REGION_NAME = env("S3_REGION", default="fr-par")
AWS_S3_USE_SSL = env("S3_USE_SSL")
AWS_S3_ADDRESSING_STYLE = "path"
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 300
AWS_S3_FILE_OVERWRITE = False
# Chiffrement au repos côté serveur (ex. "AES256"). Vide en dev.
if env("S3_SSE"):
    AWS_S3_OBJECT_PARAMETERS = {"ServerSideEncryption": env("S3_SSE")}

STORAGES = {
    "default": {"BACKEND": "storages.backends.s3.S3Storage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Données d'import des référentiels : sources/ (téléchargements) et private/ (copies licenciées).
SOLUGATION_DATA_DIR = Path(env("SOLUGATION_DATA_DIR", default=str(BASE_DIR.parent / "data")))

# Upload : liste blanche et taille max (contrôles appliqués côté API, semaine 2).
SOLUGATION_UPLOAD_MAX_OCTETS = env("UPLOAD_MAX_MO") * 1024 * 1024
SOLUGATION_UPLOAD_TYPES_AUTORISES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.oasis.opendocument.text": ".odt",
    "application/vnd.oasis.opendocument.spreadsheet": ".ods",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/xml": ".xml",  # rapports Nessus / OpenVAS
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_HANDLERS = [
    "apps.documents.upload.LimiteTailleUpload",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# Mails : console par défaut ; SMTP dès que EMAIL_HOST est défini (Mailpit en dev, relais SMTP en prod).
FRONTEND_URL = env("FRONTEND_URL", default=f"https://{SOLUGATION_DOMAINE}" if SOLUGATION_DOMAINE else "http://localhost:5173")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="SoluGation <notifications@solugation.local>")
if env("EMAIL_HOST", default=""):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
    EMAIL_TIMEOUT = 10
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.api.pagination.Pagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "apps.core.api.base.gestionnaire_exceptions",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"connexion": "10/min", "mot_de_passe": "5/hour", "mot_de_passe_lien": "30/hour",
                               "changement_mot_de_passe": "10/hour", "double_auth": "10/min"},
    "NUM_PROXIES": SOLUGATION_NB_PROXYS if SOLUGATION_PROXY_DE_CONFIANCE else None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API SoluGation",
    "DESCRIPTION": "Pilotage des homologations de sécurité.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Durcissement HTTP
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^api/sante/$"]  # sonde interne du conteneur, en HTTP
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # Préchargement HSTS (liste des navigateurs) : engagement quasi irréversible pour le domaine, laissé au choix
    # de l'exploitant.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# IA facultative, derrière apps/ai/provider.py (API compatible OpenAI). Ordre : écran d'administration (prime),
# puis ce fichier, sinon aucune IA : le produit fonctionne sans. IA_FOURNISSEUR : aucun (défaut), compatible
# (IA_URL, IA_MODELE, IA_CLE), scaleway ou mistral (raccourcis), factice (développement et tests).
# IA_ZDR_CONFIRME=True : l'administrateur accepte la responsabilité des conditions du fournisseur.
IA_FOURNISSEUR = env("IA_FOURNISSEUR", default="aucun")
IA_NOM = env("IA_NOM", default="")
IA_URL = env("IA_URL", default="")
IA_MODELE = env("IA_MODELE", default="")
IA_CLE = env("IA_CLE", default="")
IA_ZDR_CONFIRME = env.bool("IA_ZDR_CONFIRME", default=False)
IA_CLE_CHIFFREMENT = env("IA_CLE_CHIFFREMENT", default="")  # clé Fernet ; à défaut, dérivée de DJANGO_SECRET_KEY
IA_AUTORISER_RESEAU_LOCAL = env.bool("IA_AUTORISER_RESEAU_LOCAL", default=False)  # IA sur le réseau local (Ollama…)
MISTRAL_API_KEY = env("MISTRAL_API_KEY", default="")
MISTRAL_MODELE = env("MISTRAL_MODELE", default="mistral-medium-latest")
MISTRAL_URL = env("MISTRAL_URL", default="https://api.mistral.ai/v1")
MISTRAL_ZDR_CONFIRME = env.bool("MISTRAL_ZDR_CONFIRME", default=False)
# Exécution des analyses : « fil » (fil d'arrière-plan du serveur, développement) ou « taches » (service dédié
# `executer_taches`, production : survit aux redémarrages du serveur web). Synchrones en test.
IA_EXECUTION = env("IA_EXECUTION", default="fil")
IA_SYNCHRONE = env.bool("IA_SYNCHRONE", default=False)
