"""Comptes de l'organisation, gérés par son administrateur : invitation, rôle, fonction, désactivation.
Jamais de suppression (le journal d'audit référence les comptes) ; jamais de compte d'une autre organisation."""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.core.api.acces import ROLE_ADMIN, est_admin_organisation
from apps.core.api.journal import difference, journaliser
from apps.core.api.permissions import MembreOrganisation

from . import double_auth
from .models import Role, Utilisateur
from .mots_de_passe import envoyer, inviter

ROLES = ("admin", "membre", "auditeur")


class AdminStrict(BasePermission):
    message = "Réservé à l'administrateur de l'organisation."

    def has_permission(self, request, view):
        return est_admin_organisation(request.user)


class RoleOrganisationField(serializers.SlugRelatedField):
    def __init__(self, **kwargs):
        super().__init__(slug_field="code", **kwargs)

    def get_queryset(self):
        return Role.objects.filter(organisation=None, portee=Role.Portee.ORGANISATION, code__in=ROLES)


class CompteSerializer(serializers.ModelSerializer):
    role = RoleOrganisationField()
    role_libelle = serializers.CharField(source="role.libelle", read_only=True, default="")
    nom_complet = serializers.CharField(source="__str__", read_only=True)
    etat = serializers.SerializerMethodField(help_text="actif, invite (invitation non acceptée) ou desactive.")
    double_auth_active = serializers.SerializerMethodField()
    est_moi = serializers.SerializerMethodField()
    email = serializers.EmailField()

    class Meta:
        model = Utilisateur
        fields = ["id", "email", "first_name", "last_name", "nom_complet", "fonction", "role", "role_libelle", "is_active",
                  "etat", "double_auth_active", "est_moi", "last_login", "date_joined", "is_superuser"]
        read_only_fields = ["last_login", "date_joined", "is_superuser"]

    def get_etat(self, obj) -> str:
        if not obj.is_active:
            return "desactive"
        return "actif" if obj.has_usable_password() else "invite"

    def get_double_auth_active(self, obj) -> bool:
        return double_auth.active(obj)

    def get_est_moi(self, obj) -> bool:
        return obj.pk == self.context["request"].user.pk

    def validate_email(self, valeur):
        valeur = valeur.strip().lower()
        if self.instance and valeur != self.instance.email:
            raise serializers.ValidationError("L'email d'un compte ne se modifie pas : invitez la nouvelle adresse.")
        if not self.instance and Utilisateur.objects.filter(email__iexact=valeur).exists():
            raise serializers.ValidationError("Cette adresse est déjà utilisée sur cette installation.")
        return valeur

    def validate(self, attrs):
        moi = self.context["request"].user
        cible = self.instance
        if cible and cible.is_superuser and not moi.is_superuser:
            raise serializers.ValidationError("Seul un administrateur de l'installation peut modifier ce compte.")
        if cible and cible.pk == moi.pk:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError("Vous ne pouvez pas désactiver votre propre compte.")
            if "role" in attrs and attrs["role"].code != ROLE_ADMIN:
                raise serializers.ValidationError("Vous ne pouvez pas retirer votre propre rôle d'administrateur.")
        if cible and cible.role and cible.role.code == ROLE_ADMIN and cible.is_active:
            perd_admin = ("role" in attrs and attrs["role"].code != ROLE_ADMIN) or attrs.get("is_active") is False
            autres = Utilisateur.objects.filter(organisation_id=cible.organisation_id, role__code=ROLE_ADMIN,
                                                role__portee=Role.Portee.ORGANISATION, is_active=True).exclude(pk=cible.pk)
            if perd_admin and not autres.exists():
                raise serializers.ValidationError("L'organisation doit garder au moins un administrateur actif.")
        return attrs


class CompteViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                    viewsets.GenericViewSet):
    """Comptes de l'organisation (`/api/administration/comptes/`). Créer = inviter (mail d'activation)."""

    serializer_class = CompteSerializer
    permission_classes = [MembreOrganisation, AdminStrict]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Utilisateur.objects.filter(organisation_id=self.request.user.organisation_id).select_related("role") \
            .order_by("-is_active", "last_name", "first_name", "email")

    @transaction.atomic
    def perform_create(self, serializer):
        utilisateur = serializer.save(organisation=self.request.user.organisation)
        utilisateur.set_unusable_password()  # le compte s'active quand l'invité choisit son mot de passe
        utilisateur.save(update_fields=["password"])
        inviter(utilisateur, self.request.user)
        journaliser(self.request, JournalAudit.Action.CREATION, utilisateur,
                    donnees={"email": utilisateur.email, "role": utilisateur.role.code, "invitation": "envoyée"})

    @transaction.atomic
    def perform_update(self, serializer):
        diff = difference(serializer.instance, serializer.validated_data)
        if "role" in diff:
            diff["role"] = {"avant": serializer.instance.role.code if serializer.instance.role else None,
                            "apres": serializer.validated_data["role"].code}
        serializer.save()
        if diff:
            journaliser(self.request, JournalAudit.Action.MODIFICATION, serializer.instance, donnees=diff)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"], url_path="renvoyer-invitation")
    def renvoyer_invitation(self, request, pk=None):
        utilisateur = self.get_object()
        if not utilisateur.is_active or utilisateur.has_usable_password():
            return Response({"detail": "Ce compte n'a pas d'invitation en attente."}, status=status.HTTP_400_BAD_REQUEST)
        utilisateur.set_unusable_password()  # nouveau lien : le précédent devient invalide
        utilisateur.save(update_fields=["password"])
        inviter(utilisateur, request.user)
        journaliser(request, JournalAudit.Action.MODIFICATION, utilisateur, donnees={"invitation": "renvoyée"})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"], url_path="reinitialiser-double-auth")
    def reinitialiser_double_auth(self, request, pk=None):
        """Téléphone perdu, codes de secours épuisés : la personne se reconnecte avec son seul mot de passe, puis
        réactive la double authentification (imposée à la connexion si la politique l'exige)."""
        utilisateur = self.get_object()
        if utilisateur.is_superuser and not request.user.is_superuser:
            return Response({"detail": "Seul un administrateur de l'installation peut modifier ce compte."}, status=status.HTTP_400_BAD_REQUEST)
        if utilisateur.pk == request.user.pk:
            return Response({"detail": "Utilisez Mon compte pour votre propre double authentification."}, status=status.HTTP_400_BAD_REQUEST)
        double_auth.desactiver(utilisateur)
        journaliser(request, JournalAudit.Action.MODIFICATION, utilisateur, donnees={"double_authentification": "réinitialisée par l'administrateur"})
        envoyer(utilisateur, "Double authentification réinitialisée", "Double authentification réinitialisée",
                f"{request.user} a réinitialisé la double authentification de votre compte SoluGation. "
                "À votre prochaine connexion, configurez-la de nouveau depuis Mon compte.",
                note="Si vous n'avez pas demandé cette réinitialisation, prévenez immédiatement votre administrateur.")
        return Response(status=status.HTTP_204_NO_CONTENT)
