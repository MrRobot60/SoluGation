"""Invitation et mot de passe oublié : liens à usage unique et à durée limitée, envoyés par mail.

- Jetons sans stockage (générateur Django) : ils deviennent invalides dès que le mot de passe change, que le compte
  se connecte ou est désactivé. Réinitialisation : 1 heure ; invitation : 7 jours.
- Le jeton voyage dans le fragment de l'adresse (#…) : jamais envoyé au serveur ni écrit dans les journaux du proxy.
- « Mot de passe oublié » répond toujours la même chose, dans le même délai : pas d'énumération des comptes.
"""

import logging
import threading

from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections, connection, transaction
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import base36_to_int, urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import JournalAudit

from .models import Utilisateur

journal = logging.getLogger(__name__)


class Jeton(PasswordResetTokenGenerator):
    duree = 0  # secondes

    def _make_hash_value(self, utilisateur, horodatage):
        # Désactiver un compte invalide aussi ses liens en cours.
        return f"{super()._make_hash_value(utilisateur, horodatage)}{utilisateur.is_active}"

    def check_token(self, utilisateur, jeton):
        if not super().check_token(utilisateur, jeton):  # PASSWORD_RESET_TIMEOUT : borne haute commune
            return False
        try:
            emis = base36_to_int(jeton.split("-")[0])
        except ValueError:
            return False
        return self._num_seconds(self._now()) - emis <= self.duree


class JetonReinitialisation(Jeton):
    key_salt = "solugation.reinitialisation"
    duree = 60 * 60


class JetonInvitation(Jeton):
    key_salt = "solugation.invitation"
    duree = 7 * 24 * 60 * 60


JETONS = {"reinitialisation": JetonReinitialisation(), "invitation": JetonInvitation()}
PAGES = {"reinitialisation": "/mot-de-passe/nouveau", "invitation": "/invitation"}


def lien(utilisateur, nature):
    uid = urlsafe_base64_encode(force_bytes(utilisateur.pk))
    return f"{settings.FRONTEND_URL}{PAGES[nature]}#uid={uid}&jeton={JETONS[nature].make_token(utilisateur)}"


def envoyer(utilisateur, sujet, titre, message, bouton=None, url=None, note=""):
    """Un mail de compte, envoyé après validation de la transaction et hors de la requête (délai de réponse constant)."""
    contexte = {"titre": titre, "message": message, "bouton": bouton, "lien": url, "note": note,
                "logo": f"{settings.FRONTEND_URL}/marque/icone-128.png"}
    adresse = utilisateur.email

    def expedier():
        if not connection.in_atomic_block:
            close_old_connections()
        try:
            mail = EmailMultiAlternatives(f"[SoluGation] {sujet}", render_to_string("mails/compte.txt", contexte),
                                          settings.DEFAULT_FROM_EMAIL, [adresse])
            mail.attach_alternative(render_to_string("mails/compte.html", contexte), "text/html")
            mail.send()
        except Exception:
            journal.exception("Échec d'envoi d'un mail de compte")

    def apres_validation():
        if settings.MAILS_COMPTES_SYNCHRONES:  # tests : envoi immédiat, vérifiable
            expedier()
        else:
            threading.Thread(target=expedier, name="mail-compte", daemon=True).start()

    transaction.on_commit(apres_validation)


def inviter(utilisateur, invite_par):
    org = utilisateur.organisation
    envoyer(
        utilisateur, f"Invitation à rejoindre {org}", f"{invite_par} vous invite sur SoluGation",
        f"Une invitation vous attend pour rejoindre l'espace de {org} sur SoluGation, l'outil de suivi des homologations de sécurité.\n"
        "Choisissez votre mot de passe pour activer votre compte.",
        bouton="Activer mon compte", url=lien(utilisateur, "invitation"),
        note="Ce lien est personnel et valable 7 jours. Si vous n'attendiez pas cette invitation, ignorez ce message.",
    )


def utilisateur_du_lien(uid):
    try:
        return Utilisateur.objects.select_related("organisation").get(pk=force_str(urlsafe_base64_decode(uid)))
    except (ValueError, TypeError, OverflowError, Utilisateur.DoesNotExist):
        return None


class OubliSerializer(serializers.Serializer):
    email = serializers.EmailField()


class MotDePasseOublieView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "mot_de_passe"
    serializer_class = OubliSerializer

    @extend_schema(request=OubliSerializer, responses={204: None})
    def post(self, request):
        donnees = OubliSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        utilisateur = Utilisateur.objects.filter(email__iexact=donnees.validated_data["email"], is_active=True,
                                                 organisation__isnull=False, organisation__active=True).first()
        if utilisateur:
            if utilisateur.has_usable_password():
                envoyer(utilisateur, "Réinitialisation du mot de passe", "Choisir un nouveau mot de passe",
                        "Une demande de réinitialisation du mot de passe de votre compte SoluGation a été faite.",
                        bouton="Choisir un nouveau mot de passe", url=lien(utilisateur, "reinitialisation"),
                        note="Ce lien est valable 1 heure et ne sert qu'une fois. Si vous n'êtes pas à l'origine de cette "
                             "demande, ignorez ce message : votre mot de passe actuel reste valable.")
            else:  # invitation jamais acceptée : on renvoie l'invitation plutôt qu'un lien de réinitialisation
                inviter(utilisateur, "Votre administrateur")
            JournalAudit.enregistrer(utilisateur.organisation, JournalAudit.Action.MODIFICATION, utilisateur, acteur=utilisateur,
                                     donnees={"mot_de_passe": "lien de réinitialisation demandé"},
                                     ip=request.META.get("REMOTE_ADDR"), user_agent=request.META.get("HTTP_USER_AGENT", ""))
        return Response(status=status.HTTP_204_NO_CONTENT)


class LienSerializer(serializers.Serializer):
    nature = serializers.ChoiceField(choices=list(JETONS))
    uid = serializers.CharField(max_length=64)
    jeton = serializers.CharField(max_length=128)

    def validate(self, attrs):
        utilisateur = utilisateur_du_lien(attrs["uid"])
        valide = (utilisateur is not None and utilisateur.is_active and utilisateur.organisation_id
                  and utilisateur.organisation.active and JETONS[attrs["nature"]].check_token(utilisateur, attrs["jeton"])
                  # une invitation ne sert qu'à un compte jamais activé, une réinitialisation qu'à un compte actif
                  and utilisateur.has_usable_password() == (attrs["nature"] == "reinitialisation"))
        if not valide:
            raise serializers.ValidationError("Ce lien n'est plus valable (déjà utilisé, expiré ou remplacé). Demandez-en un nouveau.")
        attrs["utilisateur"] = utilisateur
        return attrs


class DefinirSerializer(LienSerializer):
    password = serializers.CharField(trim_whitespace=False, max_length=256, required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "password" in attrs:
            try:
                password_validation.validate_password(attrs["password"], attrs["utilisateur"])
            except DjangoValidationError as e:
                raise serializers.ValidationError({"password": list(e.messages)})
        return attrs


class LienView(APIView):
    """Vérifie un lien (sans `password`) ou enregistre le nouveau mot de passe (avec `password`)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "mot_de_passe_lien"
    serializer_class = DefinirSerializer

    @extend_schema(request=DefinirSerializer, responses={200: dict, 204: None})
    def post(self, request):
        donnees = DefinirSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        utilisateur, nature = donnees.validated_data["utilisateur"], donnees.validated_data["nature"]
        if "password" not in donnees.validated_data:
            return Response({"email": utilisateur.email, "prenom": utilisateur.first_name, "organisation": utilisateur.organisation.nom})
        utilisateur.set_password(donnees.validated_data["password"])  # invalide le lien et les autres sessions ouvertes
        utilisateur.save(update_fields=["password"])
        JournalAudit.enregistrer(utilisateur.organisation, JournalAudit.Action.MODIFICATION, utilisateur, acteur=utilisateur,
                                 donnees={"mot_de_passe": "invitation acceptée" if nature == "invitation" else "réinitialisé"},
                                 ip=request.META.get("REMOTE_ADDR"), user_agent=request.META.get("HTTP_USER_AGENT", ""))
        if nature == "reinitialisation":
            envoyer(utilisateur, "Mot de passe modifié", "Votre mot de passe a été modifié",
                    "Le mot de passe de votre compte SoluGation vient d'être modifié. Les autres sessions ouvertes ont été fermées.",
                    note="Si vous n'êtes pas à l'origine de ce changement, prévenez immédiatement votre administrateur.")
        return Response(status=status.HTTP_204_NO_CONTENT)
