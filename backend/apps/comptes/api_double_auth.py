"""API de la double authentification : connexion en deux temps, activation, codes de secours, politique."""

import time

from django.conf import settings
from django.contrib.auth import login
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.administration import AdminInstance
from apps.audit.models import JournalAudit
from apps.core.api.journal import journaliser
from apps.core.api.permissions import MembreOrganisation

from . import double_auth as da
from .models import ConfigurationSecurite, DoubleAuthentification, PolitiqueDoubleAuth, Utilisateur
from .mots_de_passe import envoyer


def etat(utilisateur):
    valeur = da.politique()
    return {
        "politique": valeur, "requise": da.requise(utilisateur, valeur), "active": da.active(utilisateur),
        "codes_secours_restants": da.codes_restants(utilisateur),
    }


def prevenir(utilisateur, titre, message):
    envoyer(utilisateur, titre, titre, message,
            note="Si vous n'êtes pas à l'origine de ce changement, prévenez immédiatement votre administrateur.")


class CodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)


class ConnexionCodeView(APIView):
    """Second temps de la connexion : le mot de passe a été vérifié, le code de l'application est attendu."""

    permission_classes = [AllowAny]
    throttle_scope = "double_auth"
    serializer_class = CodeSerializer

    @extend_schema(request=CodeSerializer, responses={200: dict})
    def post(self, request):
        from .api import MoiSerializer

        donnees = CodeSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        attente = request.session.get(da.SESSION_EN_ATTENTE)
        if not attente or attente["jusqua"] < time.time() or attente["essais"] >= da.ESSAIS_MAX:
            request.session.pop(da.SESSION_EN_ATTENTE, None)
            return Response({"detail": "Délai dépassé ou trop d'essais : reconnectez-vous."}, status=status.HTTP_400_BAD_REQUEST)
        utilisateur = Utilisateur.objects.filter(pk=attente["id"], is_active=True).first()
        methode = utilisateur and da.verifier(utilisateur, donnees.validated_data["code"])
        if not methode:
            attente["essais"] += 1
            request.session[da.SESSION_EN_ATTENTE] = attente
            return Response({"detail": "Code incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        del request.session[da.SESSION_EN_ATTENTE]
        login(request, utilisateur)
        request.session[da.SESSION_VERIFIEE] = True
        journaliser(request, JournalAudit.Action.CONNEXION, utilisateur, donnees={"double_authentification": methode})
        if methode == "code de secours":
            prevenir(utilisateur, "Code de secours utilisé",
                     f"Un code de secours vient d'être utilisé pour vous connecter. Il vous en reste {da.codes_restants(utilisateur)}.")
        return Response(MoiSerializer(utilisateur).data)


class MotDePasseSerializer(serializers.Serializer):
    mot_de_passe = serializers.CharField(trim_whitespace=False, max_length=256)

    def validate_mot_de_passe(self, valeur):
        if not self.context["request"].user.check_password(valeur):
            raise serializers.ValidationError("Mot de passe incorrect.")
        return valeur


def confirmer_mot_de_passe(request):
    """Les changements de double authentification redemandent le mot de passe (session laissée ouverte, volée…)."""
    MotDePasseSerializer(data=request.data, context={"request": request}).is_valid(raise_exception=True)


class EtatDoubleAuthView(APIView):
    permission_classes = [MembreOrganisation]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response(etat(request.user))


class PreparerDoubleAuthView(APIView):
    permission_classes = [MembreOrganisation]
    throttle_scope = "double_auth"
    serializer_class = MotDePasseSerializer

    @extend_schema(request=MotDePasseSerializer, responses={200: dict})
    def post(self, request):
        if da.politique() == PolitiqueDoubleAuth.DESACTIVEE:
            return Response({"detail": "La double authentification est désactivée sur cette installation."}, status=status.HTTP_400_BAD_REQUEST)
        if da.active(request.user):
            return Response({"detail": "La double authentification est déjà active."}, status=status.HTTP_400_BAD_REQUEST)
        confirmer_mot_de_passe(request)
        return Response(da.preparer(request.user))


class ActiverDoubleAuthView(APIView):
    permission_classes = [MembreOrganisation]
    throttle_scope = "double_auth"
    serializer_class = CodeSerializer

    @extend_schema(request=CodeSerializer, responses={200: dict})
    @transaction.atomic
    def post(self, request):
        donnees = CodeSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        en_cours = DoubleAuthentification.objects.filter(utilisateur=request.user, active_le__isnull=True).first()
        if en_cours is None:
            return Response({"detail": "Recommencez l'activation."}, status=status.HTTP_400_BAD_REQUEST)
        if not da.verifier_totp(en_cours, donnees.validated_data["code"]):
            return Response({"detail": "Code incorrect. Vérifiez l'heure de votre téléphone et saisissez le code affiché."},
                            status=status.HTTP_400_BAD_REQUEST)
        DoubleAuthentification.objects.filter(pk=en_cours.pk).update(active_le=timezone.now())
        codes = da.generer_codes_secours(request.user)
        request.session[da.SESSION_VERIFIEE] = True  # cette session reste ouverte ; les autres seront fermées
        journaliser(request, JournalAudit.Action.MODIFICATION, request.user, donnees={"double_authentification": "activée"})
        prevenir(request.user, "Double authentification activée",
                 "La double authentification est désormais demandée à chaque connexion à votre compte SoluGation. "
                 "Les autres sessions ouvertes ont été fermées.")
        return Response({"codes_secours": codes, **etat(request.user)})


class DesactiverDoubleAuthView(APIView):
    permission_classes = [MembreOrganisation]
    throttle_scope = "double_auth"
    serializer_class = MotDePasseSerializer

    @extend_schema(request=MotDePasseSerializer, responses={200: dict})
    def post(self, request):
        if da.requise(request.user):
            return Response({"detail": "La double authentification est obligatoire pour votre compte."}, status=status.HTTP_400_BAD_REQUEST)
        confirmer_mot_de_passe(request)
        da.desactiver(request.user)
        journaliser(request, JournalAudit.Action.MODIFICATION, request.user, donnees={"double_authentification": "désactivée"})
        prevenir(request.user, "Double authentification désactivée",
                 "La double authentification n'est plus demandée à la connexion à votre compte SoluGation.")
        return Response(etat(request.user))


class CodesSecoursView(APIView):
    permission_classes = [MembreOrganisation]
    throttle_scope = "double_auth"
    serializer_class = MotDePasseSerializer

    @extend_schema(request=MotDePasseSerializer, responses={200: dict})
    def post(self, request):
        if not da.active(request.user):
            return Response({"detail": "La double authentification n'est pas active."}, status=status.HTTP_400_BAD_REQUEST)
        confirmer_mot_de_passe(request)
        codes = da.generer_codes_secours(request.user)
        journaliser(request, JournalAudit.Action.MODIFICATION, request.user, donnees={"double_authentification": "codes de secours régénérés"})
        return Response({"codes_secours": codes, **etat(request.user)})


class PolitiqueSerializer(serializers.Serializer):
    politique_double_auth = serializers.ChoiceField(choices=[("", "Fichier de configuration"), *PolitiqueDoubleAuth.choices])


class SecuriteInstanceView(APIView):
    """Politique de double authentification de l'installation (administrateur de l'installation)."""

    permission_classes = [MembreOrganisation, AdminInstance]
    serializer_class = PolitiqueSerializer

    def reponse(self):
        config = ConfigurationSecurite.courante()
        return Response({
            "politique": da.politique(), "ecran": (config and config.politique_double_auth) or "",
            "fichier": settings.DOUBLE_AUTH_POLITIQUE, "choix": [{"cle": c, "libelle": l} for c, l in PolitiqueDoubleAuth.choices],
            "modifie_par": str(config.modifie_par) if config and config.modifie_par else "", "modifie_le": config and config.modifie_le,
        })

    @extend_schema(responses={200: dict})
    def get(self, request):
        return self.reponse()

    @extend_schema(request=PolitiqueSerializer, responses={200: dict})
    def patch(self, request):
        donnees = PolitiqueSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        config, _ = ConfigurationSecurite.objects.get_or_create(instance=1)
        avant = da.politique()
        config.politique_double_auth = donnees.validated_data["politique_double_auth"]
        config.modifie_par = request.user
        config.save()
        JournalAudit.enregistrer(organisation=request.user.organisation, action=JournalAudit.Action.MODIFICATION, objet=config,
                                 acteur=request.user, donnees={"politique_double_auth": {"avant": avant, "apres": da.politique()}},
                                 ip=request.META.get("REMOTE_ADDR"), user_agent=request.META.get("HTTP_USER_AGENT", ""))
        return self.reponse()
