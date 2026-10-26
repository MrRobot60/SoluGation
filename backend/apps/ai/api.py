"""Conclusions de l'IA : consultation et décision humaine (règle d'or : l'IA recommande, l'humain valide)."""

from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.core.api.acces import peut_decider_projet, projets_accessibles
from apps.core.api.journal import journaliser
from apps.core.api.permissions import MembreOrganisation
from apps.core.models import StatutValidation
from apps.projets.models import StatutMesure
from apps.suivi.api import signaler_nouvelle_tache
from apps.suivi.services import tache_pour_manquement

from .models import ResultatAnalyseMesure

COUVERTURE_VERS_STATUT = {
    ResultatAnalyseMesure.Couverture.COUVERT: StatutMesure.Statut.CONFORME,
    ResultatAnalyseMesure.Couverture.PARTIEL: StatutMesure.Statut.PARTIEL,
    ResultatAnalyseMesure.Couverture.ABSENT: StatutMesure.Statut.MANQUANT,
}


class ResultatSerializer(serializers.ModelSerializer):
    mesure_identifiant = serializers.CharField(source="mesure.identifiant", read_only=True)
    document_nom = serializers.CharField(source="document.nom_original", read_only=True, default="")
    valide_par_nom = serializers.CharField(source="valide_par.__str__", read_only=True, default="")

    class Meta:
        model = ResultatAnalyseMesure
        fields = ["id", "projet", "analyse", "mesure", "mesure_identifiant", "document", "document_nom", "couverture",
                  "justification", "extraits", "confiance", "statut_validation", "valide_par", "valide_par_nom",
                  "valide_le", "commentaire_validation", "cree_le"]
        read_only_fields = fields


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[StatutValidation.VALIDE, StatutValidation.REJETE])
    commentaire = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ResultatViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """`?projet=`, `?mesure=`, `?statut_validation=a_valider`. Aucune écriture hors de l'action `statuer`."""

    serializer_class = ResultatSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        qs = (ResultatAnalyseMesure.objects.filter(projet__in=projets_accessibles(self.request.user))
              .select_related("mesure", "document", "valide_par").order_by("-cree_le"))
        p = self.request.query_params
        for champ in ("projet", "mesure", "statut_validation"):
            if p.get(champ):
                qs = qs.filter(**{f"{champ}_id" if champ != "statut_validation" else champ: p[champ]})
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
