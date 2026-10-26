"""Conclusions de l'IA : consultation et décision humaine (règle d'or : l'IA recommande, l'humain valide)."""

from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.core.api.acces import peut_decider_projet, peut_ecrire_projet, projets_accessibles
from apps.core.api.journal import journaliser
from apps.core.api.permissions import MembreOrganisation
from apps.core.models import StatutValidation
from apps.documents.models import DocumentDepose
from apps.projets.models import Projet, StatutMesure
from apps.suivi.api import signaler_nouvelle_tache
from apps.suivi.services import tache_pour_manquement

from .analyse import creer_analyse, documents_du_projet, en_cours
from .models import AnalyseIA, ResultatAnalyseMesure
from .provider import IAIndisponible

COUVERTURE_VERS_STATUT = {
    ResultatAnalyseMesure.Couverture.COUVERT: StatutMesure.Statut.CONFORME,
    ResultatAnalyseMesure.Couverture.PARTIEL: StatutMesure.Statut.PARTIEL,
    ResultatAnalyseMesure.Couverture.ABSENT: StatutMesure.Statut.MANQUANT,
}


class ResultatSerializer(serializers.ModelSerializer):
    mesure_identifiant = serializers.CharField(source="mesure.identifiant", read_only=True)
    document_nom = serializers.CharField(source="document.nom_original", read_only=True, default="")
    valide_par_nom = serializers.CharField(source="valide_par.__str__", read_only=True, default="")

    mesure_intitule = serializers.CharField(source="mesure.intitule", read_only=True)
    referentiel_code = serializers.CharField(source="mesure.referentiel.code", read_only=True)
    fournisseur = serializers.CharField(source="analyse.fournisseur", read_only=True)

    class Meta:
        model = ResultatAnalyseMesure
        fields = ["id", "projet", "analyse", "fournisseur", "mesure", "mesure_identifiant", "mesure_intitule",
                  "referentiel_code", "document", "document_nom", "couverture",
                  "justification", "extraits", "confiance", "statut_validation", "valide_par", "valide_par_nom",
                  "valide_le", "commentaire_validation", "cree_le"]
        read_only_fields = fields


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[StatutValidation.VALIDE, StatutValidation.REJETE])
    commentaire = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ResultatViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """`?projet=`, `?mesure=`, `?analyse=`, `?statut_validation=a_valider`, `?actuels=1` (dernière analyse terminée). Aucune écriture hors de l'action `statuer`."""

    serializer_class = ResultatSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        qs = (ResultatAnalyseMesure.objects.filter(projet__in=projets_accessibles(self.request.user))
              .select_related("mesure__referentiel", "document", "valide_par", "analyse").order_by("-cree_le"))
        p = self.request.query_params
        for champ in ("projet", "mesure", "statut_validation", "analyse"):
            if p.get(champ):
                qs = qs.filter(**{f"{champ}_id" if champ != "statut_validation" else champ: p[champ]})
        if p.get("actuels"):  # une nouvelle analyse remplace les propositions des précédentes
            derniere = (AnalyseIA.objects.filter(projet=OuterRef("projet"), etat=AnalyseIA.Etat.TERMINEE,
                                                 type_analyse=AnalyseIA.Type.ANALYSE_DOCUMENTAIRE)
                        .order_by("-fin_le").values("pk")[:1])
            qs = qs.filter(analyse=Subquery(derniere))
        return qs

    @action(detail=True, methods=["post"], serializer_class=DecisionSerializer)
    @transaction.atomic
    def statuer(self, request, pk=None):
        resultat = self.get_object()
        if not peut_decider_projet(request.user, resultat.projet):
            raise PermissionDenied("Seuls le RSSI, l'autorité d'homologation ou l'administrateur peuvent statuer.")
        if resultat.statut_validation != StatutValidation.A_VALIDER:
            return Response({"detail": "Cette conclusion a déjà fait l'objet d'une décision."},
                            status=status.HTTP_409_CONFLICT)
        donnees = DecisionSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        decision, commentaire = donnees.validated_data["decision"], donnees.validated_data.get("commentaire", "")

        if decision == StatutValidation.VALIDE:
            resultat.valider(request.user, commentaire)
            evaluation, _ = StatutMesure.objects.update_or_create(
                projet=resultat.projet, mesure=resultat.mesure,
                defaults={
                    "statut": COUVERTURE_VERS_STATUT[resultat.couverture],
                    "justification": f"Proposition de l'IA validée : {resultat.justification}",
                    "resultat_analyse": resultat, "evalue_par": request.user, "evalue_le": timezone.now(),
                },
            )
            if tache := tache_pour_manquement(evaluation):
                signaler_nouvelle_tache(request, tache)
        else:
            resultat.rejeter(request.user, commentaire)
        journaliser(request, JournalAudit.Action.VALIDATION_IA, resultat, resultat.projet, {
            "decision": decision, "mesure": resultat.mesure.identifiant, "couverture": resultat.couverture,
            "commentaire": commentaire,
        })
        return Response(ResultatSerializer(resultat).data)


class AnalyseSerializer(serializers.ModelSerializer):
    demandee_par_nom = serializers.CharField(source="demandee_par.__str__", read_only=True)
    nb_resultats = serializers.IntegerField(read_only=True, default=0)
    nb_a_valider = serializers.IntegerField(read_only=True, default=0)
    documents_analyses = serializers.SerializerMethodField()

    class Meta:
        model = AnalyseIA
        fields = ["id", "projet", "type_analyse", "etat", "fournisseur", "modele", "version_prompt", "erreur",
                  "demandee_par_nom", "debut_le", "fin_le", "cree_le", "nb_resultats", "nb_a_valider", "documents_analyses"]
        read_only_fields = fields

    def get_documents_analyses(self, obj) -> list:
        return (obj.resultat_brut or {}).get("documents", [])


class LancementSerializer(serializers.Serializer):
    projet = serializers.PrimaryKeyRelatedField(queryset=Projet.objects.none())
    documents = serializers.PrimaryKeyRelatedField(queryset=DocumentDepose.objects.none(), many=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        utilisateur = self.context["request"].user
        self.fields["projet"].queryset = projets_accessibles(utilisateur)
        self.fields["documents"].child_relation.queryset = DocumentDepose.objects.filter(projet__in=projets_accessibles(utilisateur))

    def validate(self, attrs):
        projet = attrs["projet"]
        if any(d.projet_id != projet.pk for d in attrs.get("documents", [])):
            raise serializers.ValidationError({"documents": "Documents hors du projet."})
        return attrs


class AnalyseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Analyses IA d'un projet (`?projet=`). POST {projet, documents?} lance l'analyse documentaire : sans
    `documents`, la dernière version de chaque document du projet. Exécution en arrière-plan : suivre `etat`."""

    serializer_class = AnalyseSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        qs = (AnalyseIA.objects.filter(projet__in=projets_accessibles(self.request.user))
              .select_related("demandee_par")
              .annotate(nb_resultats=Count("resultats"),
                        nb_a_valider=Count("resultats", filter=Q(resultats__statut_validation=StatutValidation.A_VALIDER)))
              .order_by("-cree_le"))
        if self.request.query_params.get("projet"):
            qs = qs.filter(projet_id=self.request.query_params["projet"])
        return qs

    def create(self, request, *args, **kwargs):
        demande = LancementSerializer(data=request.data, context={"request": request})
        demande.is_valid(raise_exception=True)
        projet = demande.validated_data["projet"]
        if not peut_ecrire_projet(request.user, projet):
            raise PermissionDenied("Lecture seule sur ce projet.")
        if not projet.organisation.ia_activee:
            raise PermissionDenied("L'IA est désactivée pour votre organisation.")
        if en_cours(projet):
            return Response({"detail": "Une analyse est déjà en cours sur ce projet."}, status=status.HTTP_409_CONFLICT)
        documents = demande.validated_data.get("documents") or documents_du_projet(projet)
        if not documents:
            return Response({"detail": "Aucun document déposé à analyser."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                analyse = creer_analyse(request.user, projet, documents)
                journaliser(request, JournalAudit.Action.CREATION, analyse, projet, {
                    "type": analyse.type_analyse, "fournisseur": analyse.fournisseur, "modele": analyse.modele,
                    "documents": [{"nom": d.nom_original, "sha256": d.sha256} for d in documents],
                })
        except IAIndisponible as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(AnalyseSerializer(self.get_queryset().get(pk=analyse.pk)).data, status=status.HTTP_202_ACCEPTED)
