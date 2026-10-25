"""Authentification par session Django (cookie HttpOnly + CSRF), adaptée à un frontend servi sur le même domaine."""

from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import JournalAudit
from apps.core.api.acces import est_admin_organisation
from apps.core.api.journal import difference, journaliser
from apps.core.api.permissions import AdminOrganisation, MembreOrganisation

from .models import Organisation, Role, Utilisateur


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
    lecture_seule = serializers.BooleanField(source="est_lecture_seule", read_only=True)

    class Meta(UtilisateurSerializer.Meta):
        fields = UtilisateurSerializer.Meta.fields + ["organisation", "est_admin", "lecture_seule"]
        read_only_fields = fields

    def get_est_admin(self, obj) -> bool:
        return est_admin_organisation(obj)


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
        login(request, utilisateur)
        journaliser(request, JournalAudit.Action.CONNEXION, utilisateur)
        return Response(MoiSerializer(utilisateur).data)


class DeconnexionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MoiView(APIView):
    permission_classes = [MembreOrganisation]
    serializer_class = MoiSerializer

    def get(self, request):
        return Response(MoiSerializer(request.user).data)


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
