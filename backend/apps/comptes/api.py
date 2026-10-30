"""Authentification par session Django (cookie HttpOnly + CSRF), adaptée à un frontend servi sur le même domaine."""

import time

from django.contrib.auth import authenticate, login, logout, password_validation, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import JournalAudit
from apps.core.api.acces import est_admin_organisation, projets_accessibles
from apps.core.api.journal import difference, journaliser
from apps.core.api.permissions import AdminOrganisation, MembreOrganisation

from . import double_auth
from .models import Organisation, Role, Utilisateur
from .mots_de_passe import envoyer


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "libelle", "portee", "lecture_seule"]


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id", "nom", "slug", "secteur", "siret", "ia_activee"]
        read_only_fields = ["id", "slug"]


class UtilisateurSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    nom_complet = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Utilisateur
        fields = ["id", "email", "first_name", "last_name", "nom_complet", "fonction", "role", "is_active"]
        read_only_fields = fields


class MoiSerializer(UtilisateurSerializer):
    organisation = OrganisationSerializer(read_only=True)
    est_admin = serializers.SerializerMethodField()
    est_admin_instance = serializers.BooleanField(source="is_superuser", read_only=True)
    lecture_seule = serializers.BooleanField(source="est_lecture_seule", read_only=True)
    ia_disponible = serializers.SerializerMethodField(help_text="IA configurée sur l'installation et activée pour l'organisation.")
    visite_terminee = serializers.SerializerMethodField(help_text="Visite guidée terminée ou passée.")
    double_auth = serializers.SerializerMethodField(help_text="Politique de l'installation, obligation et état pour ce compte.")

    class Meta(UtilisateurSerializer.Meta):
        fields = UtilisateurSerializer.Meta.fields + ["organisation", "est_admin", "est_admin_instance", "lecture_seule", "ia_disponible",
                                                      "visite_terminee", "double_auth"]
        read_only_fields = fields

    def get_est_admin(self, obj) -> bool:
        return est_admin_organisation(obj)

    def get_ia_disponible(self, obj) -> bool:
        from apps.ai.provider import ia_disponible

        return bool(obj.organisation and obj.organisation.ia_activee and ia_disponible())


    def get_double_auth(self, obj) -> dict:
        politique = double_auth.politique()
        return {"politique": politique, "requise": double_auth.requise(obj, politique), "active": double_auth.active(obj)}

    def get_visite_terminee(self, obj) -> bool:
        return obj.visite_terminee_le is not None


class ConnexionSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """Pose le cookie CSRF ; le frontend le renvoie ensuite dans l'en-tête X-CSRFToken."""

    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: dict})
    def get(self, request):
        return Response({"csrftoken": get_token(request)})


class ConnexionView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "connexion"
    serializer_class = ConnexionSerializer

    @extend_schema(request=ConnexionSerializer, responses={200: MoiSerializer})
    def post(self, request):
        donnees = ConnexionSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        utilisateur = authenticate(request, **donnees.validated_data)
        if utilisateur is None or not utilisateur.organisation_id:
            # Message identique dans tous les cas : pas d'énumération des comptes.
            return Response({"detail": "Identifiants invalides."}, status=status.HTTP_400_BAD_REQUEST)
        if double_auth.active(utilisateur):
            # Mot de passe correct, session pas encore ouverte : le code de l'application est attendu (auth/connexion/code/).
            request.session.cycle_key()
            request.session[double_auth.SESSION_EN_ATTENTE] = {
                "id": str(utilisateur.pk), "jusqua": time.time() + double_auth.DELAI_CODE, "essais": 0}
            return Response({"double_authentification": True})
        login(request, utilisateur)
        journaliser(request, JournalAudit.Action.CONNEXION, utilisateur)
        return Response(MoiSerializer(utilisateur).data)


class DeconnexionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ["first_name", "last_name", "fonction"]


class MoiView(APIView):
    """Le compte connecté. PATCH : son nom et sa fonction (l'email et le rôle relèvent de l'administrateur)."""

    permission_classes = [MembreOrganisation]
    serializer_class = MoiSerializer

    def get(self, request):
        return Response(MoiSerializer(request.user).data)

    @extend_schema(request=ProfilSerializer, responses={200: MoiSerializer})
    def patch(self, request):
        profil = ProfilSerializer(request.user, data=request.data, partial=True)
        profil.is_valid(raise_exception=True)
        diff = difference(request.user, profil.validated_data)
        profil.save()
        if diff:
            journaliser(request, JournalAudit.Action.MODIFICATION, request.user, donnees=diff)
        return Response(MoiSerializer(request.user).data)


class ChangementMotDePasseSerializer(serializers.Serializer):
    actuel = serializers.CharField(trim_whitespace=False, max_length=256)
    nouveau = serializers.CharField(trim_whitespace=False, max_length=256)

    def validate_actuel(self, valeur):
        if not self.context["request"].user.check_password(valeur):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return valeur

    def validate(self, attrs):
        if attrs["nouveau"] == attrs["actuel"]:
            raise serializers.ValidationError({"nouveau": ["Le nouveau mot de passe doit être différent de l'actuel."]})
        try:
            password_validation.validate_password(attrs["nouveau"], self.context["request"].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"nouveau": list(e.messages)})
        return attrs


class ChangementMotDePasseView(APIView):
    """Changement par le titulaire : mot de passe actuel exigé ; cette session reste ouverte, les autres sont fermées."""

    permission_classes = [MembreOrganisation]
    serializer_class = ChangementMotDePasseSerializer
    throttle_scope = "changement_mot_de_passe"  # freine la recherche du mot de passe actuel depuis une session volée

    @extend_schema(request=ChangementMotDePasseSerializer, responses={204: None})
    def post(self, request):
        donnees = ChangementMotDePasseSerializer(data=request.data, context={"request": request})
        donnees.is_valid(raise_exception=True)
        utilisateur = request.user
        utilisateur.set_password(donnees.validated_data["nouveau"])
        utilisateur.save(update_fields=["password"])
        update_session_auth_hash(request, utilisateur)
        journaliser(request, JournalAudit.Action.MODIFICATION, utilisateur, donnees={"mot_de_passe": "changé par le titulaire"})
        envoyer(utilisateur, "Mot de passe modifié", "Votre mot de passe a été modifié",
                "Le mot de passe de votre compte SoluGation vient d'être modifié depuis l'écran Mon compte. "
                "Les autres sessions ouvertes ont été fermées.",
                note="Si vous n'êtes pas à l'origine de ce changement, prévenez immédiatement votre administrateur.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class VisiteSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["demarrer", "terminer", "revoir"])


class VisiteView(APIView):
    """Visite guidée. `demarrer` renvoie le projet d'exemple (créé au besoin ; un compte en lecture seule visite
    un projet existant), `terminer` la marque finie ou passée, `revoir` la relance."""

    permission_classes = [MembreOrganisation]
    serializer_class = VisiteSerializer

    def post(self, request):
        from apps.projets.exemple import projet_exemple  # import tardif : projets dépend de comptes

        action = VisiteSerializer(data=request.data)
        action.is_valid(raise_exception=True)
        utilisateur = request.user
        match action.validated_data["action"]:
            case "terminer":
                utilisateur.visite_terminee_le = timezone.now()
                utilisateur.save(update_fields=["visite_terminee_le"])
            case "revoir":
                utilisateur.visite_terminee_le = None
                utilisateur.save(update_fields=["visite_terminee_le"])
            case "demarrer":
                if utilisateur.est_lecture_seule:
                    projet = projets_accessibles(utilisateur).order_by("-modifie_le").first()
                else:
                    projet = projet_exemple(utilisateur)
                return Response({"projet": projet and str(projet.id)})
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganisationView(APIView):
    """L'organisation de l'utilisateur. Modification (dont l'option IA) réservée à l'administrateur."""

    permission_classes = [MembreOrganisation, AdminOrganisation]
    serializer_class = OrganisationSerializer

    def get(self, request):
        return Response(OrganisationSerializer(request.user.organisation).data)

    def patch(self, request):
        org = request.user.organisation
        serializer = OrganisationSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        diff = difference(org, serializer.validated_data)
        serializer.save()
        if diff:
            journaliser(request, JournalAudit.Action.MODIFICATION, org, donnees=diff)
        return Response(serializer.data)


class UtilisateurViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Annuaire des membres de l'organisation (pour désigner les acteurs d'un projet)."""

    serializer_class = UtilisateurSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        return Utilisateur.objects.filter(organisation_id=self.request.user.organisation_id).select_related("role")


class RoleViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = RoleSerializer
    permission_classes = [MembreOrganisation]
    pagination_class = None

    def get_queryset(self):
        qs = Role.objects.filter(Q(organisation=None) | Q(organisation_id=self.request.user.organisation_id))
        if portee := self.request.query_params.get("portee"):
            qs = qs.filter(portee=portee)
        return qs
