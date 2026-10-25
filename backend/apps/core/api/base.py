"""Classes de base des vues et serializers : filtrage par organisation, contrôle des liens entre objets,
journal d'audit automatique sur chaque écriture."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from rest_framework import serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.audit.models import JournalAudit

from .acces import peut_ecrire_projet, projets_accessibles
from .journal import difference, instantane, journaliser
from .permissions import EcritureSelonRole, MembreOrganisation


def gestionnaire_exceptions(exc, context):
    """Les ValidationError levées par les modèles (garde-fous d'isolation) deviennent des 400, pas des 500."""
    if isinstance(exc, DjangoValidationError):
        exc = serializers.ValidationError(exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages})
    if isinstance(exc, ProtectedError):
        return Response({"detail": "Objet encore utilisé par d'autres données : suppression impossible."},
                        status=status.HTTP_409_CONFLICT)
    return exception_handler(exc, context)


class ProjetAccessibleField(serializers.PrimaryKeyRelatedField):
    """FK vers un projet : seuls les projets accessibles à l'utilisateur sont acceptés (sinon « objet inexistant »)."""

    def get_queryset(self):
        return projets_accessibles(self.context["request"].user)


class ProjetScopedSerializer(serializers.ModelSerializer):
    """Vérifie que les objets liés appartiennent au même projet et que l'utilisateur peut y écrire."""

    projet = ProjetAccessibleField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        projet = attrs.get("projet") or getattr(self.instance, "projet", None)
        if self.instance is not None and "projet" in attrs and attrs["projet"] != self.instance.projet:
            raise serializers.ValidationError({"projet": "Un objet ne change pas de projet."})
        if not peut_ecrire_projet(self.context["request"].user, projet):
            raise PermissionDenied("Écriture non autorisée sur ce projet.")
        for champ in getattr(self.Meta.model, "champs_meme_projet", ()):
            cible = attrs.get(champ)
            if cible is not None and cible.projet_id != projet.id:
                raise serializers.ValidationError({champ: "Objet inexistant."})
        return attrs


class JournaliseMixin:
    """Création, modification et suppression tracées dans le journal d'audit (avec diff)."""

    def _projet(self, objet):
        return objet if objet.__class__.__name__ == "Projet" else getattr(objet, "projet", None)

    def perform_create(self, serializer):
        objet = serializer.save()
        journaliser(self.request, JournalAudit.Action.CREATION, objet, self._projet(objet),
                    instantane(serializer.validated_data))

    def perform_update(self, serializer):
        diff = difference(serializer.instance, serializer.validated_data)
        objet = serializer.save()
        if diff:
            journaliser(self.request, JournalAudit.Action.MODIFICATION, objet, self._projet(objet), diff)

    def perform_destroy(self, instance):
        journaliser(self.request, JournalAudit.Action.SUPPRESSION, instance, self._projet(instance), {"repr": str(instance)})
        instance.delete()


class ProjetScopedViewSet(JournaliseMixin, viewsets.ModelViewSet):
    """Objets d'un projet. Filtrage systématique sur les projets accessibles ; `?projet=<id>` pour restreindre."""

    permission_classes = [MembreOrganisation, EcritureSelonRole]

    def get_queryset(self):
        qs = super().get_queryset().filter(projet__in=projets_accessibles(self.request.user))
        if not qs.ordered:  # pagination stable
            qs = qs.order_by("cree_le")
        if projet := self.request.query_params.get("projet"):
            qs = qs.filter(projet_id=projet)
        return qs
