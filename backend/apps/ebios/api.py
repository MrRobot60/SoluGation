"""API EBIOS RM. Tous les objets passent par ProjetScopedSerializer (même projet, droits d'écriture, relations
multiples contrôlées) et ne s'écrivent que si EBIOS RM est activé sur le projet."""

from django.db import transaction
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.core.api.acces import peut_ecrire_projet, projets_accessibles
from apps.core.api.base import JournaliseMixin, ProjetScopedSerializer, ProjetScopedViewSet
from apps.core.api.journal import journaliser
from apps.core.api.permissions import EcritureSelonRole, MembreOrganisation
from apps.suivi.api import lien_tache
from apps.suivi.notifications import acteurs_concernes, notifier

from . import models as m
from .services import ateliers, preremplir_socle, synchroniser_risque_residuel, synthese, tache_pour_mesure, zone_menace


class EbiosSerializer(ProjetScopedSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        projet = attrs.get("projet") or self.instance.projet
        if not projet.ebios_active:
            raise serializers.ValidationError({"projet": "EBIOS RM n'est pas activé pour ce projet."})
        return attrs


def serializer_pour(modele, base=EbiosSerializer, **attributs):
    meta = type("Meta", (), {"model": modele, "exclude": ["organisation"], "read_only_fields": ["cree_le", "modifie_le"]})
    return type(f"{modele.__name__}Serializer", (base,), {"Meta": meta, **attributs})


class AtelierSerializer(EbiosSerializer):
    libelle = serializers.CharField(source="get_numero_display", read_only=True)

    class Meta:
        model = m.AtelierEBIOS
        exclude = ["organisation"]
        read_only_fields = ["numero", "cree_le", "modifie_le"]


class EcartSocleSerializer(EbiosSerializer):
    class Meta:
        model = m.EcartSocle
        exclude = ["organisation"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        projet = attrs.get("projet") or self.instance.projet
        refs = set(projet.referentiels.values_list("pk", flat=True))
        for champ, ref_id in (("referentiel", getattr(attrs.get("referentiel"), "pk", None)),
                              ("mesure", getattr(attrs.get("mesure"), "referentiel_id", None))):
            if ref_id is not None and ref_id not in refs:
                raise serializers.ValidationError({champ: "Hors des référentiels du projet."})
        return attrs


class PartiePrenanteSerializer(EbiosSerializer):
    niveau_menace = serializers.FloatField(read_only=True)
    zone = serializers.SerializerMethodField()

    class Meta:
        model = m.PartiePrenante
        exclude = ["organisation"]

    def get_zone(self, obj) -> str:
        return zone_menace(obj.niveau_menace)


class ScenarioStrategiqueSerializer(EbiosSerializer):
    class Meta:
        model = m.ScenarioStrategique
        exclude = ["organisation"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        couple = attrs.get("couple") or getattr(self.instance, "couple", None)
        if couple is not None and not couple.retenu:
            raise serializers.ValidationError({"couple": "Ce couple SR/OV n'est pas retenu à l'atelier 2."})
        return attrs


class RisqueSerializer(EbiosSerializer):
    """Gravité reprise du scénario stratégique et vraisemblance du scénario opérationnel quand elles ne sont pas
    saisies ; un risque accepté sans cotation résiduelle garde sa cotation initiale."""

    gravite = serializers.IntegerField(min_value=1, max_value=4, required=False)
    vraisemblance = serializers.IntegerField(min_value=1, max_value=4, required=False)
    niveau = serializers.SerializerMethodField()
    niveau_residuel = serializers.SerializerMethodField()

    class Meta:
        model = m.RisqueEBIOS
        exclude = ["organisation"]

    def get_niveau(self, obj) -> int:
        return obj.gravite * obj.vraisemblance

    def get_niveau_residuel(self, obj) -> int | None:
        return obj.gravite_residuelle * obj.vraisemblance_residuelle if obj.gravite_residuelle and obj.vraisemblance_residuelle else None

    def validate(self, attrs):
        attrs = super().validate(attrs)
        ss = attrs.get("scenario_strategique") or getattr(self.instance, "scenario_strategique", None)
        so = attrs.get("scenario_operationnel", getattr(self.instance, "scenario_operationnel", None))
        if so is not None and so.chemin.scenario_id != ss.pk:
            raise serializers.ValidationError({"scenario_operationnel": "Ce scénario opérationnel ne découle pas du scénario stratégique choisi."})
        if self.instance is None:
            attrs.setdefault("gravite", ss.gravite)
            if "vraisemblance" not in attrs:
                if so is None:
                    raise serializers.ValidationError({"vraisemblance": "À coter, ou à reprendre d'un scénario opérationnel."})
                attrs["vraisemblance"] = so.vraisemblance
        if attrs.get("option_traitement", getattr(self.instance, "option_traitement", "")) == m.RisqueEBIOS.Option.ACCEPTER:
            for champ in ("gravite", "vraisemblance"):
                if attrs.get(f"{champ}_residuelle", getattr(self.instance, f"{champ}_residuelle", None)) is None:
                    attrs[f"{champ}_residuelle"] = attrs.get(champ, getattr(self.instance, champ, None))
        return attrs


class MesureTraitementSerializer(EbiosSerializer):
    tache_statut = serializers.CharField(source="tache.get_statut_display", read_only=True, default="")

    class Meta:
        model = m.MesureTraitement
        exclude = ["organisation"]
        read_only_fields = ["tache"]


class EbiosViewSet(ProjetScopedViewSet):
    pass


def vue_pour(modele, serializer):
    return type(f"{modele.__name__}ViewSet", (EbiosViewSet,), {"queryset": modele.objects.all(), "serializer_class": serializer})


class RisqueViewSet(EbiosViewSet):
    queryset = m.RisqueEBIOS.objects.all()
    serializer_class = RisqueSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            super().perform_create(serializer)
            synchroniser_risque_residuel(serializer.instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            super().perform_update(serializer)
            synchroniser_risque_residuel(serializer.instance)


class MesureTraitementViewSet(EbiosViewSet):
    """Chaque mesure du PACS crée sa tâche dans le plan d'action (suivie ensuite comme les autres)."""

    queryset = m.MesureTraitement.objects.select_related("tache")
    serializer_class = MesureTraitementSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            super().perform_create(serializer)
            tache = tache_pour_mesure(serializer.instance)
            journaliser(self.request, JournalAudit.Action.CREATION, tache, tache.projet, {"titre": tache.titre, "origine": "ebios"})
            notifier(tache.projet, auteur=self.request.user, type_evenement="tache.creee", titre=f"Nouvelle tâche (EBIOS RM) : {tache.titre}",
                     message=f"Mesure de traitement du risque. Échéance : {tache.echeance:%d/%m/%Y}.", lien=lien_tache(tache),
                     destinataires=acteurs_concernes(tache.projet, responsable=tache.responsable))


class AtelierViewSet(JournaliseMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):
    """Les cinq ateliers d'un projet (créés à la première consultation) : statut, date, notes, participants."""

    serializer_class = AtelierSerializer
    permission_classes = [MembreOrganisation, EcritureSelonRole]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        qs = m.AtelierEBIOS.objects.filter(projet__in=projets_accessibles(self.request.user)).order_by("numero")
        if projet := self.request.query_params.get("projet"):
            qs = qs.filter(projet_id=projet)
        return qs

    def list(self, request, *args, **kwargs):
        if projet := projets_accessibles(request.user).filter(pk=request.query_params.get("projet") or None, ebios_active=True).first():
            ateliers(projet)
        return super().list(request, *args, **kwargs)


class EbiosProjetViewSet(viewsets.ViewSet):
    """`synthese/?projet=` : avancement, alertes, matrice, cartographie. `socle/` POST {projet} : pré-remplit le
    socle depuis les évaluations de conformité."""

    permission_classes = [MembreOrganisation]

    def _projet(self, request, identifiant):
        projet = projets_accessibles(request.user).filter(pk=identifiant or None).first() if identifiant else None
        if projet is None:
            raise NotFound("Projet inexistant.")
        if not projet.ebios_active:
            raise PermissionDenied("EBIOS RM n'est pas activé pour ce projet.")
        return projet

    @action(detail=False, methods=["get"])
    def synthese(self, request):
        return Response(synthese(self._projet(request, request.query_params.get("projet"))))

    @action(detail=False, methods=["post"])
    def socle(self, request):
        projet = self._projet(request, request.data.get("projet"))
        if not peut_ecrire_projet(request.user, projet):
            raise PermissionDenied("Lecture seule sur ce projet.")
        with transaction.atomic():
            crees = preremplir_socle(projet)
            if crees:
                journaliser(request, JournalAudit.Action.CREATION, projet, projet, {"ebios_socle": len(crees)})
        return Response({"crees": len(crees)}, status=status.HTTP_201_CREATED if crees else status.HTTP_200_OK)


ROUTES = [
    ("ebios/ateliers", AtelierViewSet, "ebios-atelier"),
    ("ebios/valeurs-metier", vue_pour(m.ValeurMetier, serializer_pour(m.ValeurMetier)), "ebios-valeur-metier"),
    ("ebios/biens-supports", vue_pour(m.BienSupport, serializer_pour(m.BienSupport)), "ebios-bien-support"),
    ("ebios/evenements-redoutes", vue_pour(m.EvenementRedoute, serializer_pour(m.EvenementRedoute)), "ebios-evenement-redoute"),
    ("ebios/ecarts-socle", vue_pour(m.EcartSocle, EcartSocleSerializer), "ebios-ecart-socle"),
    ("ebios/sources-risque", vue_pour(m.SourceRisque, serializer_pour(m.SourceRisque)), "ebios-source-risque"),
    ("ebios/objectifs-vises", vue_pour(m.ObjectifVise, serializer_pour(m.ObjectifVise)), "ebios-objectif-vise"),
    ("ebios/couples", vue_pour(m.CoupleSROV, serializer_pour(m.CoupleSROV)), "ebios-couple"),
    ("ebios/parties-prenantes", vue_pour(m.PartiePrenante, PartiePrenanteSerializer), "ebios-partie-prenante"),
    ("ebios/scenarios-strategiques", vue_pour(m.ScenarioStrategique, ScenarioStrategiqueSerializer), "ebios-scenario-strategique"),
    ("ebios/chemins", vue_pour(m.CheminAttaque, serializer_pour(m.CheminAttaque)), "ebios-chemin"),
    ("ebios/mesures-ecosysteme", vue_pour(m.MesureEcosysteme, serializer_pour(m.MesureEcosysteme)), "ebios-mesure-ecosysteme"),
    ("ebios/scenarios-operationnels", vue_pour(m.ScenarioOperationnel, serializer_pour(m.ScenarioOperationnel)), "ebios-scenario-operationnel"),
    ("ebios/risques", RisqueViewSet, "ebios-risque"),
    ("ebios/mesures-traitement", MesureTraitementViewSet, "ebios-mesure-traitement"),
    ("ebios", EbiosProjetViewSet, "ebios"),
]
