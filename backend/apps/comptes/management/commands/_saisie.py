"""Saisie du mot de passe pour les commandes de comptes : jamais en argument (il resterait dans l'historique
du shell), mais demandé de façon masquée, ou lu dans SOLUGATION_MOT_DE_PASSE pour une installation automatisée."""

import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError


def mot_de_passe(utilisateur=None):
    valeur = os.environ.get("SOLUGATION_MOT_DE_PASSE")
    if not valeur:
        valeur = getpass.getpass("Mot de passe : ")
        if valeur != getpass.getpass("Confirmation : "):
            raise CommandError("Les deux saisies diffèrent.")
    try:
        validate_password(valeur, utilisateur)
    except ValidationError as e:
        raise CommandError(" ".join(e.messages)) from None
    return valeur
