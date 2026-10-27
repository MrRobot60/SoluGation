"""Protection de la configuration IA saisie à l'écran.

- Clé d'API chiffrée (Fernet). Clé de chiffrement : `IA_CLE_CHIFFREMENT` si fournie, sinon dérivée de
  `DJANGO_SECRET_KEY` (changer celle-ci oblige à ressaisir la clé d'API).
- SSRF : une URL saisie à l'écran ne doit pas faire appeler par le serveur une adresse interne (réseau local,
  boucle locale, métadonnées cloud). Refus par défaut, sauf `IA_AUTORISER_RESEAU_LOCAL=True` (ex. Ollama sur le
  même réseau). Contrôle à l'enregistrement et à chaque appel (le nom de domaine peut changer d'adresse)."""

import base64
import hashlib
import ipaddress
import socket
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class UrlRefusee(Exception):
    pass


def _fernet():
    cle = settings.IA_CLE_CHIFFREMENT or base64.urlsafe_b64encode(
        hashlib.sha256(f"solugation-ia:{settings.SECRET_KEY}".encode()).digest()).decode()
    return Fernet(cle.encode() if isinstance(cle, str) else cle)


def chiffrer(texte):
    return _fernet().encrypt(texte.encode()).decode() if texte else ""


def dechiffrer(jeton):
    if not jeton:
        return ""
    try:
        return _fernet().decrypt(jeton.encode()).decode()
    except InvalidToken:
        return ""  # clé de chiffrement changée : la clé d'API est à ressaisir


def verifier_url(url):
    """Lève UrlRefusee si l'URL vise une adresse interne (sauf autorisation explicite)."""
    morceaux = urlsplit(url)
    if morceaux.scheme not in ("https", "http") or not morceaux.hostname:
        raise UrlRefusee("Adresse invalide : http(s)://hôte/chemin attendu.")
    if morceaux.username or morceaux.password:
        raise UrlRefusee("Pas d'identifiants dans l'adresse : utilisez le champ clé d'API.")
    if settings.IA_AUTORISER_RESEAU_LOCAL:
        return
    if morceaux.scheme != "https":
        raise UrlRefusee("HTTPS obligatoire (HTTP n'est accepté que pour un réseau local autorisé dans la configuration).")
    try:
        adresses = {info[4][0] for info in socket.getaddrinfo(morceaux.hostname, morceaux.port or 443)}
    except socket.gaierror:
        raise UrlRefusee("Nom de domaine introuvable.") from None
    for brute in adresses:
        ip = ipaddress.ip_address(brute.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise UrlRefusee("Adresse interne refusée (réseau local, boucle locale ou métadonnées). "
                             "Pour un fournisseur local, autorisez IA_AUTORISER_RESEAU_LOCAL dans la configuration.")
