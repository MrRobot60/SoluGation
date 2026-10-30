"""Double authentification par application (TOTP, RFC 6238 : Aegis, FreeOTP, Google Authenticator, 1Password…).

- Politique choisie par l'administrateur de l'installation (écran, sinon DOUBLE_AUTH_POLITIQUE) : désactivée,
  facultative, obligatoire pour les administrateurs, obligatoire pour tous.
- Secret chiffré en base (Fernet) ; un code accepté ne resservira pas (anti-rejeu) ; codes de secours à usage
  unique dont seule l'empreinte est conservée.
- La session porte la preuve du second facteur (`SESSION_VERIFIEE`) : sans elle, le middleware refuse l'accès,
  y compris à l'admin Django (dont le formulaire ne demande que le mot de passe).
"""

import base64
import hashlib
import hmac
import secrets

import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils import timezone

from apps.core.api.acces import est_admin_organisation

from .models import CodeSecours, ConfigurationSecurite, DoubleAuthentification, PolitiqueDoubleAuth

EMETTEUR = "SoluGation"
NB_CODES_SECOURS = 10
SESSION_VERIFIEE = "double_auth_verifiee"
SESSION_EN_ATTENTE = "double_auth_en_attente"  # mot de passe correct, code attendu : {"id", "jusqua", "essais"}
DELAI_CODE = 5 * 60
ESSAIS_MAX = 5


def politique():
    config = ConfigurationSecurite.courante()
    valeur = (config and config.politique_double_auth) or settings.DOUBLE_AUTH_POLITIQUE
    return valeur if valeur in PolitiqueDoubleAuth.values else PolitiqueDoubleAuth.FACULTATIVE


def active(utilisateur):
    """Second facteur demandé à la connexion : configuré par le compte, et la fonction n'est pas désactivée."""
    if politique() == PolitiqueDoubleAuth.DESACTIVEE:
        return False
    return DoubleAuthentification.objects.filter(utilisateur=utilisateur, active_le__isnull=False).exists()


def requise(utilisateur, valeur=None):
    valeur = valeur or politique()
    return valeur == PolitiqueDoubleAuth.TOUS or (
        valeur == PolitiqueDoubleAuth.ADMINISTRATEURS and (utilisateur.is_superuser or est_admin_organisation(utilisateur)))


def _fernet():
    cle = settings.SOLUGATION_CLE_CHIFFREMENT or base64.urlsafe_b64encode(
        hashlib.sha256(f"solugation-double-auth:{settings.SECRET_KEY}".encode()).digest()).decode()
    return Fernet(cle.encode() if isinstance(cle, str) else cle)


def _secret(double_auth):
    try:
        return _fernet().decrypt(double_auth.secret_chiffre.encode()).decode()
    except InvalidToken:  # clé de chiffrement changée : l'administrateur réinitialise la double authentification
        return None


def preparer(utilisateur):
    """Nouveau secret, non actif tant qu'un code n'a pas été confirmé. Renvoie de quoi configurer l'application."""
    secret = pyotp.random_base32()
    DoubleAuthentification.objects.update_or_create(
        utilisateur=utilisateur, defaults={"secret_chiffre": _fernet().encrypt(secret.encode()).decode(), "active_le": None, "dernier_pas": 0})
    uri = pyotp.TOTP(secret).provisioning_uri(name=utilisateur.email, issuer_name=EMETTEUR)
    return {"secret": secret, "uri": uri, "qr_svg": segno.make(uri, error="m").svg_inline(scale=4, border=2, dark="#000", light="#fff")}


def verifier_totp(double_auth, code):
    """Code à 6 chiffres de l'application (± 30 s de décalage d'horloge toléré), une seule utilisation."""
    secret = _secret(double_auth)
    code = "".join(c for c in str(code) if c.isdigit())
    if not secret or len(code) != 6:
        return False
    totp = pyotp.TOTP(secret)
    maintenant = int(timezone.now().timestamp()) // totp.interval
    for pas in (maintenant - 1, maintenant, maintenant + 1):
        if pas > double_auth.dernier_pas and hmac.compare_digest(totp.generate_otp(pas), code):
            # Mise à jour conditionnelle : deux requêtes simultanées avec le même code, une seule réussit.
            return bool(DoubleAuthentification.objects.filter(pk=double_auth.pk, dernier_pas__lt=pas).update(dernier_pas=pas))
    return False


def _empreinte(code):
    return hashlib.sha256(code.replace("-", "").replace(" ", "").lower().encode()).hexdigest()


def generer_codes_secours(utilisateur):
    """Remplace les codes de secours ; renvoie les codes en clair (affichés une seule fois)."""
    CodeSecours.objects.filter(utilisateur=utilisateur).delete()
    codes = []
    for _ in range(NB_CODES_SECOURS):
        brut = secrets.token_hex(5)  # 40 bits, ex. 3f9a1-c07e2
        codes.append(f"{brut[:5]}-{brut[5:]}")
        CodeSecours.objects.create(utilisateur=utilisateur, empreinte=_empreinte(brut))
    return codes


def utiliser_code_secours(utilisateur, code):
    empreinte = _empreinte(str(code))
    for candidat in CodeSecours.objects.filter(utilisateur=utilisateur, utilise_le__isnull=True):
        if hmac.compare_digest(candidat.empreinte, empreinte):
            return bool(CodeSecours.objects.filter(pk=candidat.pk, utilise_le__isnull=True).update(utilise_le=timezone.now()))
    return False


def verifier(utilisateur, code):
    """Renvoie la méthode acceptée (« application » ou « code de secours »), ou None."""
    double_auth = DoubleAuthentification.objects.filter(utilisateur=utilisateur, active_le__isnull=False).first()
    if double_auth is None:
        return None
    if verifier_totp(double_auth, code):
        return "application"
    if utiliser_code_secours(utilisateur, code):
        return "code de secours"
    return None


def codes_restants(utilisateur):
    return CodeSecours.objects.filter(utilisateur=utilisateur, utilise_le__isnull=True).count()


def desactiver(utilisateur):
    DoubleAuthentification.objects.filter(utilisateur=utilisateur).delete()
    CodeSecours.objects.filter(utilisateur=utilisateur).delete()
