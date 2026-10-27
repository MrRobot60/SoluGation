"""Bibliothèque de référentiels : bibliothèque commune (sources libres) + imports privés de l'organisation
(copie licenciée, ex. ISO 27001), jamais visibles d'une autre organisation. Le texte officiel n'est servi que
si le référentiel l'embarque (en version commerciale, une norme payante n'expose qu'identifiant et intitulé)."""

from django.db.models import Count, Min, Q
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.core.api.permissions import MembreOrganisation

from .models import CorrespondanceMesure, Mesure, Referentiel


def referentiels_accessibles(utilisateur):
    """Bibliothèque commune + imports privés de l'organisation."""
    return Referentiel.objects.filter(Q(organisation=None) | Q(organisation_id=utilisateur.organisation_id), actif=True)


def correspondances_accessibles(utilisateur):
    refs = referentiels_accessibles(utilisateur)
    return CorrespondanceMesure.objects.filter(
        Q(organisation=None) | Q(organisation_id=utilisateur.organisation_id),
        mesure_source__referentiel__in=refs, mesure_cible__referentiel__in=refs,
    )


def texte_visible(mesure):
    return mesure.texte_officiel if mesure.referentiel.texte_embarque else None


class ReferentielSerializer(serializers.ModelSerializer):
    nb_mesures = serializers.IntegerField(read_only=True)
    prive = serializers.SerializerMethodField()
    nouvelle_version = serializers.PrimaryKeyRelatedField(source="remplace_par", read_only=True)
    nouvelle_version_libelle = serializers.SerializerMethodField()
    licence_libelle = serializers.CharField(source="get_licence_display", read_only=True)
    nb_projets = serializers.SerializerMethodField()

    class Meta:
        model = Referentiel
        fields = ["id", "code", "nom", "version", "editeur", "url_source", "licence", "licence_libelle", "texte_embarque",
                  "date_publication", "date_import", "empreinte_source", "nouvelle_version", "nouvelle_version_libelle", "prive",
                  "nb_mesures", "nb_projets"]

    def get_prive(self, obj) -> bool:
        return obj.organisation_id is not None

    def get_nouvelle_version_libelle(self, obj) -> str:
        return str(obj.remplace_par) if obj.remplace_par_id else ""

    def get_nb_projets(self, obj) -> int:
        """Projets de l'organisation qui utilisent ce référentiel (jamais ceux d'une autre organisation)."""
        requete = self.context.get("request")
        if requete is None:
            return 0
        return obj.projets.filter(organisation_id=requete.user.organisation_id).count()


class MesureSerializer(serializers.ModelSerializer):
    texte_officiel = serializers.SerializerMethodField()
    referentiel_code = serializers.CharField(source="referentiel.code", read_only=True)
    referentiel_nom = serializers.CharField(source="referentiel.nom", read_only=True)

    class Meta:
        model = Mesure
        fields = ["id", "referentiel", "referentiel_code", "referentiel_nom", "identifiant", "intitule", "categorie", "niveaux",
                  "texte_officiel", "ordre"]

    def get_texte_officiel(self, obj) -> str | None:
        return texte_visible(obj)


class ReferentielViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReferentielSerializer
    permission_classes = [MembreOrganisation]
    pagination_class = None

    def get_queryset(self):
        return referentiels_accessibles(self.request.user).select_related("remplace_par").annotate(nb_mesures=Count("mesures"))

    @action(detail=True, methods=["get"])
    def categories(self, request, pk=None):
        """Catégories (chapitres) dans l'ordre du référentiel, avec leur nombre de mesures."""
        ref = self.get_object()
        lignes = (Mesure.objects.filter(referentiel=ref).values("categorie").annotate(n=Count("id"), ordre=Min("ordre")).order_by("ordre"))
        return Response([{"categorie": l["categorie"] or "Sans catégorie", "nb_mesures": l["n"]} for l in lignes])


class MesureViewSet(viewsets.ReadOnlyModelViewSet):
    """`?referentiel=<id>`, `?categorie=…`, `?q=` (identifiant, intitulé, et texte quand il est embarqué).
    La fiche (`retrieve`) ajoute les correspondances et l'état de la mesure dans les projets de l'utilisateur."""

    serializer_class = MesureSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        qs = Mesure.objects.filter(referentiel__in=referentiels_accessibles(self.request.user)).select_related("referentiel")
        p = self.request.query_params
        if p.get("referentiel"):
            qs = qs.filter(referentiel_id=p["referentiel"])
        if p.get("categorie"):
            qs = qs.filter(categorie=p["categorie"])
        if q := p.get("q", "").strip():
            qs = qs.filter(Q(identifiant__icontains=q) | Q(intitule__icontains=q)
                           | Q(texte_officiel__icontains=q, referentiel__texte_embarque=True))
        return qs.order_by("referentiel__code", "ordre")

    def retrieve(self, request, *args, **kwargs):
        from apps.core.api.acces import projets_accessibles
        from apps.projets.models import StatutMesure

        mesure = self.get_object()
        donnees = MesureSerializer(mesure).data
        liens = (correspondances_accessibles(request.user).filter(Q(mesure_source=mesure) | Q(mesure_cible=mesure))
                 .select_related("mesure_source__referentiel", "mesure_cible__referentiel"))
        donnees["correspondances"] = [{
            "id": str(c.pk), "type": c.type_correspondance, "type_libelle": c.get_type_correspondance_display(),
            "sens": "sortante" if c.mesure_source_id == mesure.pk else "entrante", "origine": c.get_origine_display(),
            "reference": c.reference, "modifiable": c.organisation_id == request.user.organisation_id,
            "mesure": MesureSerializer(c.mesure_cible if c.mesure_source_id == mesure.pk else c.mesure_source).data,
        } for c in liens]
        donnees["projets"] = [
            {"projet": str(s.projet_id), "projet_nom": s.projet.nom, "statut": s.statut, "statut_libelle": s.get_statut_display()}
            for s in StatutMesure.objects.filter(mesure=mesure, projet__in=projets_accessibles(request.user)).select_related("projet")
        ]
        return Response(donnees)


class CorrespondanceSerializer(serializers.ModelSerializer):
    mesure_source = serializers.PrimaryKeyRelatedField(queryset=Mesure.objects.none())
    mesure_cible = serializers.PrimaryKeyRelatedField(queryset=Mesure.objects.none())

    class Meta:
        model = CorrespondanceMesure
        fields = ["id", "mesure_source", "mesure_cible", "type_correspondance", "reference"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        accessibles = Mesure.objects.filter(referentiel__in=referentiels_accessibles(self.context["request"].user))
        self.fields["mesure_source"].queryset = accessibles
        self.fields["mesure_cible"].queryset = accessibles

    def validate(self, attrs):
        source, cible = attrs["mesure_source"], attrs["mesure_cible"]
        if source.referentiel_id == cible.referentiel_id:
            raise serializers.ValidationError("Une correspondance relie deux référentiels différents.")
        organisation = self.context["request"].user.organisation_id
        if CorrespondanceMesure.objects.filter(Q(organisation=None) | Q(organisation_id=organisation)).filter(
                Q(mesure_source=source, mesure_cible=cible) | Q(mesure_source=cible, mesure_cible=source)).exists():
            raise serializers.ValidationError("Ces deux mesures sont déjà reliées.")
        return attrs


class CorrespondanceViewSet(mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Correspondances propres à l'organisation (saisie manuelle). Les tables communes ne se modifient pas ici."""

    serializer_class = CorrespondanceSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        return CorrespondanceMesure.objects.filter(organisation_id=self.request.user.organisation_id)

    def _verifier(self):
        if self.request.user.est_lecture_seule:
            raise PermissionDenied("Lecture seule.")

    def perform_create(self, serializer):
        self._verifier()
        c = serializer.save(organisation=self.request.user.organisation, origine=CorrespondanceMesure.Origine.MANUELLE)
        JournalAudit.enregistrer(organisation=self.request.user.organisation, action=JournalAudit.Action.CREATION, objet=c,
                                 acteur=self.request.user, donnees={"source": str(c.mesure_source), "cible": str(c.mesure_cible),
                                                                     "type": c.type_correspondance})

    def perform_destroy(self, instance):
        self._verifier()
        JournalAudit.enregistrer(organisation=self.request.user.organisation, action=JournalAudit.Action.SUPPRESSION, objet=instance,
                                 acteur=self.request.user, donnees={"source": str(instance.mesure_source), "cible": str(instance.mesure_cible)})
        instance.delete()
