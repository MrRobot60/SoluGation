from django.db.models import Count, Q
from rest_framework import serializers, viewsets

from apps.core.api.permissions import MembreOrganisation

from .models import Mesure, Referentiel


def referentiels_accessibles(utilisateur):
    """Bibliothèque commune + imports privés de l'organisation."""
    return Referentiel.objects.filter(Q(organisation=None) | Q(organisation_id=utilisateur.organisation_id), actif=True)


class ReferentielSerializer(serializers.ModelSerializer):
    nb_mesures = serializers.IntegerField(read_only=True)
    prive = serializers.SerializerMethodField()
    nouvelle_version = serializers.PrimaryKeyRelatedField(source="remplace_par", read_only=True)

    class Meta:
        model = Referentiel
        fields = ["id", "code", "nom", "version", "editeur", "url_source", "licence", "texte_embarque",
                  "date_import", "empreinte_source", "nouvelle_version", "prive", "nb_mesures"]

    def get_prive(self, obj) -> bool:
        return obj.organisation_id is not None


class MesureSerializer(serializers.ModelSerializer):
    texte_officiel = serializers.SerializerMethodField()

    class Meta:
        model = Mesure
        fields = ["id", "referentiel", "identifiant", "intitule", "categorie", "niveaux", "texte_officiel", "ordre"]

    def get_texte_officiel(self, obj) -> str | None:
        return obj.texte_officiel if obj.referentiel.texte_embarque else None


class ReferentielViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReferentielSerializer
    permission_classes = [MembreOrganisation]
    pagination_class = None

    def get_queryset(self):
        return referentiels_accessibles(self.request.user).annotate(nb_mesures=Count("mesures"))


class MesureViewSet(viewsets.ReadOnlyModelViewSet):
    """`?referentiel=<id>`, `?categorie=…`, `?q=` (identifiant ou intitulé)."""

    serializer_class = MesureSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        qs = Mesure.objects.filter(referentiel__in=referentiels_accessibles(self.request.user)).select_related("referentiel")
        p = self.request.query_params
        if p.get("referentiel"):
            qs = qs.filter(referentiel_id=p["referentiel"])
        if p.get("categorie"):
            qs = qs.filter(categorie=p["categorie"])
        if p.get("q"):
            qs = qs.filter(Q(identifiant__icontains=p["q"]) | Q(intitule__icontains=p["q"]))
        return qs.order_by("referentiel", "ordre")
