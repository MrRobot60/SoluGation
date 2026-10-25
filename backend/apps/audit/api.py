from django.db.models import Q
from rest_framework import serializers, viewsets

from apps.core.api.acces import est_admin_organisation, projets_accessibles
from apps.core.api.permissions import MembreOrganisation

from .models import JournalAudit


class JournalAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalAudit
        fields = ["id", "horodatage", "acteur", "acteur_repr", "action", "projet", "objet_type", "objet_id",
                  "objet_repr", "donnees", "hash_precedent", "hash"]


class JournalAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """Historique en lecture seule. Entrées hors projet (connexions, réglages) : administrateur uniquement."""

    serializer_class = JournalAuditSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        u = self.request.user
        filtre = Q(projet__in=projets_accessibles(u))
        if est_admin_organisation(u):
            filtre |= Q(projet=None)
        qs = JournalAudit.objects.filter(filtre, organisation_id=u.organisation_id).order_by("-id")
        if projet := self.request.query_params.get("projet"):
            qs = qs.filter(projet_id=projet)
        return qs
