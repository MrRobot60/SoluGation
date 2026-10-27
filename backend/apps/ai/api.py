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
from apps.core.api.base import NomField
from apps.core.api.journal import journaliser
from apps.core.api.permissions import MembreOrganisation
from apps.core.models import StatutValidation
from apps.documents.models import DocumentDepose
from apps.projets.models import Projet, StatutMesure
from apps.suivi.api import signaler_nouvelle_tache
from apps.suivi.models import Tache
from apps.suivi.services import TACHES_CLOSES, preuve_generique
from apps.suivi.services import tache_pour_manquement

from .analyse import creer_analyse, documents_du_projet, en_cours
from .models import AnalyseIA, RecommandationIA, ResultatAnalyseMesure
from .recommandations import creer_recommandations, taches_a_traiter
from .provider import IAIndisponible

COUVERTURE_VERS_STATUT = {
    ResultatAnalyseMesure.Couverture.COUVERT: StatutMesure.Statut.CONFORME,
    ResultatAnalyseMesure.Couverture.PARTIEL: StatutMesure.Statut.PARTIEL,
    ResultatAnalyseMesure.Couverture.ABSENT: StatutMesure.Statut.MANQUANT,
}


class ResultatSerializer(serializers.ModelSerializer):
    mesure_identifiant = serializers.CharField(source="mesure.identifiant", read_only=True)
    document_nom = serializers.CharField(source="document.nom_original", read_only=True, default="")
    valide_par_nom = NomField(source="valide_par")

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
    demandee_par_nom = NomField(source="demandee_par")
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
    type_analyse = serializers.ChoiceField(choices=[AnalyseIA.Type.ANALYSE_DOCUMENTAIRE, AnalyseIA.Type.RECOMMANDATION],
                                           default=AnalyseIA.Type.ANALYSE_DOCUMENTAIRE)
    documents = serializers.PrimaryKeyRelatedField(queryset=DocumentDepose.objects.none(), many=True, required=False)
    taches = serializers.PrimaryKeyRelatedField(queryset=Tache.objects.none(), many=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        accessibles = projets_accessibles(self.context["request"].user)
        self.fields["projet"].queryset = accessibles
        self.fields["documents"].child_relation.queryset = DocumentDepose.objects.filter(projet__in=accessibles)
        self.fields["taches"].child_relation.queryset = Tache.objects.filter(projet__in=accessibles)

    def validate(self, attrs):
        projet = attrs["projet"]
        if any(o.projet_id != projet.pk for champ in ("documents", "taches") for o in attrs.get(champ, [])):
            raise serializers.ValidationError("Éléments hors du projet.")
        return attrs


class AnalyseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Analyses IA d'un projet (`?projet=`, `?type_analyse=`). POST {projet, type_analyse?, documents?, taches?} :
    analyse documentaire (défaut : dernière version de chaque document) ou recommandations (défaut : tâches
    ouvertes sans recommandation en attente ni acceptée). Exécution en arrière-plan : suivre `etat`."""

    serializer_class = AnalyseSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        qs = (AnalyseIA.objects.filter(projet__in=projets_accessibles(self.request.user))
              .select_related("demandee_par")
              .annotate(nb_resultats=Count("resultats", distinct=True) + Count("recommandations", distinct=True),
                        nb_a_valider=Count("resultats", filter=Q(resultats__statut_validation=StatutValidation.A_VALIDER), distinct=True)
                        + Count("recommandations", filter=Q(recommandations__statut_validation=StatutValidation.A_VALIDER), distinct=True))
              .order_by("-cree_le"))
        for champ in ("projet", "type_analyse"):
            if self.request.query_params.get(champ):
                qs = qs.filter(**{"projet_id" if champ == "projet" else champ: self.request.query_params[champ]})
        return qs

    def create(self, request, *args, **kwargs):
        demande = LancementSerializer(data=request.data, context={"request": request})
        demande.is_valid(raise_exception=True)
        projet = demande.validated_data["projet"]
        if not peut_ecrire_projet(request.user, projet):
            raise PermissionDenied("Lecture seule sur ce projet.")
        if not projet.organisation.ia_activee:
            raise PermissionDenied("L'IA est désactivée pour votre organisation.")
        type_analyse = demande.validated_data["type_analyse"]
        if en_cours(projet, type_analyse):
            return Response({"detail": "Une analyse du même type est déjà en cours sur ce projet."},
                            status=status.HTTP_409_CONFLICT)
        if type_analyse == AnalyseIA.Type.RECOMMANDATION:
            choisies = demande.validated_data.get("taches")
            elements = taches_a_traiter(projet, [t.pk for t in choisies] if choisies else None)
            if not elements:
                return Response({"detail": "Aucune tâche ouverte sans recommandation."}, status=status.HTTP_400_BAD_REQUEST)
            trace = {"taches": [t.titre for t in elements]}
        else:
            elements = demande.validated_data.get("documents") or documents_du_projet(projet)
            if not elements:
                return Response({"detail": "Aucun document déposé à analyser."}, status=status.HTTP_400_BAD_REQUEST)
            trace = {"documents": [{"nom": d.nom_original, "sha256": d.sha256} for d in elements]}
        try:
            with transaction.atomic():
                creer = creer_recommandations if type_analyse == AnalyseIA.Type.RECOMMANDATION else creer_analyse
                analyse = creer(request.user, projet, elements)
                journaliser(request, JournalAudit.Action.CREATION, analyse, projet, {
                    "type": analyse.type_analyse, "fournisseur": analyse.fournisseur, "modele": analyse.modele, **trace,
                })
        except IAIndisponible as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(AnalyseSerializer(self.get_queryset().get(pk=analyse.pk)).data, status=status.HTTP_202_ACCEPTED)


class RecommandationSerializer(serializers.ModelSerializer):
    mesure_identifiant = serializers.CharField(source="mesure.identifiant", read_only=True, default="")
    fournisseur = serializers.CharField(source="analyse.fournisseur", read_only=True)
    valide_par_nom = NomField(source="valide_par")

    class Meta:
        model = RecommandationIA
        fields = ["id", "projet", "analyse", "fournisseur", "tache", "mesure", "mesure_identifiant", "texte", "etapes",
                  "preuve_suggeree", "effort", "statut_validation", "valide_par", "valide_par_nom", "valide_le",
                  "commentaire_validation", "cree_le"]
        read_only_fields = fields


class RecommandationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """`?projet=`, `?tache=`, `?statut_validation=`. Décision par l'action `statuer` (membres pouvant écrire)."""

    serializer_class = RecommandationSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        qs = (RecommandationIA.objects.filter(projet__in=projets_accessibles(self.request.user))
              .select_related("mesure", "analyse", "valide_par").order_by("-cree_le"))
        p = self.request.query_params
        for champ in ("projet", "tache", "statut_validation"):
            if p.get(champ):
                qs = qs.filter(**{f"{champ}_id" if champ != "statut_validation" else champ: p[champ]})
        return qs

    @action(detail=True, methods=["post"], serializer_class=DecisionSerializer)
    @transaction.atomic
    def statuer(self, request, pk=None):
        reco = self.get_object()
        if not peut_ecrire_projet(request.user, reco.projet):
            raise PermissionDenied("Lecture seule sur ce projet.")
        if reco.statut_validation != StatutValidation.A_VALIDER:
            return Response({"detail": "Cette recommandation a déjà fait l'objet d'une décision."},
                            status=status.HTTP_409_CONFLICT)
        donnees = DecisionSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        decision, commentaire = donnees.validated_data["decision"], donnees.validated_data.get("commentaire", "")
        completes = []
        if decision == StatutValidation.VALIDE:
            reco.valider(request.user, commentaire)
            tache = reco.tache
            if tache and tache.statut not in TACHES_CLOSES:
                # La recommandation complète la tâche sans jamais effacer ce qu'un humain a saisi : les étapes
                # s'ajoutent à la description, la preuve ne remplace qu'une preuve vide ou restée générique.
                etapes = "\n".join(f"{i}. {e}" for i, e in enumerate(reco.etapes, 1))
                ajout = f"Recommandation acceptée par {request.user} : {reco.texte}\n{etapes}"
                tache.description = f"{tache.description.rstrip()}\n\n{ajout}" if tache.description.strip() else ajout
                completes.append("description")
                generique = preuve_generique(tache.mesure) if tache.mesure else ""
                if reco.preuve_suggeree and tache.preuve_attendue.strip() in ("", generique):
                    tache.preuve_attendue = reco.preuve_suggeree
                    completes.append("preuve_attendue")
                if completes:
                    tache.save(update_fields=[*completes, "modifie_le"])
                    journaliser(request, JournalAudit.Action.MODIFICATION, tache, tache.projet, {
                        "champs": completes, "source": "recommandation IA acceptée", "recommandation": str(reco.pk),
                    })
        else:
            reco.rejeter(request.user, commentaire)
        journaliser(request, JournalAudit.Action.VALIDATION_IA, reco, reco.projet, {
            "decision": decision, "tache": str(reco.tache_id), "commentaire": commentaire, "champs_completes": completes,
        })
        return Response(RecommandationSerializer(reco).data)
