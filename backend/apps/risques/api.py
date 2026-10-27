"""Registre des risques résiduels et dérogations. Saisie par les membres qui peuvent écrire ; décisions
(accepter, refuser, clore, révoquer) réservées au RSSI, à l'autorité d'homologation et à l'administrateur,
datées, nominatives, motivées et tracées au journal. Une décision ne vaut que pour ce qui a été décidé :
modifier un risque accepté lève l'acceptation, une dérogation décidée ne se modifie plus."""

from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.core.api.acces import peut_decider_projet
from apps.core.api.base import ProjetScopedSerializer, ProjetScopedViewSet
from apps.core.api.journal import journaliser
from apps.projets.api import ChampFiltre, mesures_accessibles, nom_acteur
from apps.suivi.notifications import acteurs_concernes, notifier

from .models import Derogation, RisqueResiduel

DECISIONNAIRES = ("rssi", "autorite-homologation")
CHAMPS_COTES = ("intitule", "description", "gravite", "vraisemblance")


def lien(projet, onglet, objet):
    return f"/projets/{projet.pk}/risques?onglet={onglet}&element={objet.pk}"


def expirer_derogations(projets=None, aujourd_hui=None):
    """Dérogations acceptées dont la date d'expiration est passée → « expirée » (tracé au journal)."""
    qs = Derogation.objects.filter(statut=Derogation.Statut.ACCEPTEE, date_expiration__lt=aujourd_hui or date.today())
    if projets is not None:
        qs = qs.filter(projet__in=projets)
    expirees = list(qs.select_related("projet__organisation"))
    for d in expirees:
        d.statut = Derogation.Statut.EXPIREE
        d.save(update_fields=["statut"])
        JournalAudit.enregistrer(organisation=d.projet.organisation, action=JournalAudit.Action.MODIFICATION, objet=d,
                                 projet=d.projet, donnees={"statut": "expiree", "date_expiration": d.date_expiration.isoformat()})
    return expirees


def _mesure_du_projet(attrs, instance):
    projet = attrs.get("projet") or instance.projet
    mesures = [attrs["mesure"]] if attrs.get("mesure") else list(attrs.get("mesures", []))
    refs = set(projet.referentiels.values_list("pk", flat=True))
    if any(m.referentiel_id not in refs for m in mesures):
        raise serializers.ValidationError({"mesure": "Mesure hors des référentiels du projet."})


class RisqueSerializer(ProjetScopedSerializer):
    mesures = ChampFiltre(mesures_accessibles, many=True, required=False)
    niveau = serializers.IntegerField(read_only=True)
    proprietaire_nom = serializers.SerializerMethodField()
    accepte_par_nom = serializers.CharField(source="accepte_par.__str__", read_only=True, default="")
    revue_depassee = serializers.SerializerMethodField()
    nb_derogations = serializers.IntegerField(source="derogations.count", read_only=True)

    class Meta:
        model = RisqueResiduel
        exclude = ["organisation"]
        read_only_fields = ["origine", "risque_ebios", "accepte_par", "accepte_le", "motif_acceptation"]

    def get_proprietaire_nom(self, obj) -> str:
        return nom_acteur(obj.proprietaire)

    def get_revue_depassee(self, obj) -> bool:
        return bool(obj.date_revue and obj.date_revue < date.today() and obj.statut != RisqueResiduel.Statut.CLOS)

    def validate_statut(self, valeur):
        # Accepter et clore sont des décisions (action « decider ») ; un risque décidé se rouvre par la même voie.
        if valeur in (RisqueResiduel.Statut.ACCEPTE, RisqueResiduel.Statut.CLOS):
            raise serializers.ValidationError("Accepter ou clore un risque est une décision : utilisez « Décider ».")
        if self.instance and self.instance.statut in (RisqueResiduel.Statut.ACCEPTE, RisqueResiduel.Statut.CLOS) and valeur != self.instance.statut:
            raise serializers.ValidationError("Risque décidé : rouvrez-le d'abord.")
        return valeur

    def validate(self, attrs):
        attrs = super().validate(attrs)
        _mesure_du_projet(attrs, self.instance)
        return attrs


class DerogationSerializer(ProjetScopedSerializer):
    mesure = ChampFiltre(mesures_accessibles, required=False, allow_null=True)
    cible = serializers.SerializerMethodField()
    demandee_par_nom = serializers.CharField(source="demandee_par.__str__", read_only=True)
    decidee_par_nom = serializers.CharField(source="decidee_par.__str__", read_only=True, default="")

    class Meta:
        model = Derogation
        exclude = ["organisation"]
        read_only_fields = ["statut", "demandee_par", "decidee_par", "date_decision", "commentaire_decision"]

    def get_cible(self, obj) -> str:
        if obj.mesure_id:
            return f"{obj.mesure.referentiel.code} {obj.mesure.identifiant} — {obj.mesure.intitule}"[:200]
        return f"Risque : {obj.risque.intitule}" if obj.risque_id else ""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None and self.instance.statut != Derogation.Statut.DEMANDEE:
            raise serializers.ValidationError("Une dérogation décidée ne se modifie plus : faites une nouvelle demande.")
        risque = attrs.get("risque", getattr(self.instance, "risque", None))
        mesure = attrs.get("mesure", getattr(self.instance, "mesure", None))
        if risque is None and mesure is None:
            raise serializers.ValidationError("Une dérogation porte sur une mesure ou sur un risque.")
        if not str(attrs.get("motif", getattr(self.instance, "motif", ""))).strip():
            raise serializers.ValidationError({"motif": "Motif requis."})
        _mesure_du_projet(attrs, self.instance)
        return attrs


class DecisionRisqueSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["accepter", "clore", "rouvrir"])
    motif = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    date_revue = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["decision"] == "accepter":
            if not attrs.get("motif", "").strip():
                raise serializers.ValidationError({"motif": "Motivez l'acceptation du risque."})
            if not attrs.get("date_revue") or attrs["date_revue"] <= date.today():
                raise serializers.ValidationError({"date_revue": "Fixez une date de revue future."})
        return attrs


class DecisionDerogationSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["accepter", "refuser", "revoquer"])
    commentaire = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    date_expiration = serializers.DateField(required=False, allow_null=True)


class RisqueViewSet(ProjetScopedViewSet):
    """`?projet=`, `?statut=`. Pas de suppression d'un risque décidé (il fait partie de l'historique)."""

    queryset = RisqueResiduel.objects.select_related("proprietaire__utilisateur", "accepte_par")
    serializer_class = RisqueSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by("-gravite", "-vraisemblance", "intitule")
        if statut := self.request.query_params.get("statut"):
            qs = qs.filter(statut__in=statut.split(","))
        return qs

    def perform_create(self, serializer):
        serializer.validated_data["origine"] = RisqueResiduel.Origine.MANUELLE
        super().perform_create(serializer)

    def perform_update(self, serializer):
        r = serializer.instance
        recote = r.statut == RisqueResiduel.Statut.ACCEPTE and any(
            champ in serializer.validated_data and serializer.validated_data[champ] != getattr(r, champ) for champ in CHAMPS_COTES)
        if recote:  # le risque n'est plus celui qui a été accepté
            serializer.validated_data.update(statut=RisqueResiduel.Statut.IDENTIFIE, accepte_par=None, accepte_le=None, motif_acceptation="")
        super().perform_update(serializer)
        if recote:
            journaliser(self.request, JournalAudit.Action.DECISION, r, r.projet, {"decision": "acceptation levée", "cause": "risque modifié"})

    def perform_destroy(self, instance):
        if instance.statut in (RisqueResiduel.Statut.ACCEPTE, RisqueResiduel.Statut.CLOS) or instance.derogations.exists():
            raise PermissionDenied("Un risque décidé ou faisant l'objet d'une dérogation ne se supprime pas.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"], serializer_class=DecisionRisqueSerializer)
    @transaction.atomic
    def decider(self, request, pk=None):
        r = self.get_object()
        if not peut_decider_projet(request.user, r.projet):
            raise PermissionDenied("Seuls le RSSI, l'autorité d'homologation ou l'administrateur décident.")
        d = DecisionRisqueSerializer(data=request.data)
        d.is_valid(raise_exception=True)
        decision, motif = d.validated_data["decision"], d.validated_data.get("motif", "")
        if decision == "accepter":
            r.statut, r.accepte_par, r.accepte_le = RisqueResiduel.Statut.ACCEPTE, request.user, timezone.now()
            r.motif_acceptation, r.date_revue = motif, d.validated_data["date_revue"]
        elif decision == "clore":
            r.statut = RisqueResiduel.Statut.CLOS
        else:
            r.statut, r.accepte_par, r.accepte_le, r.motif_acceptation = RisqueResiduel.Statut.IDENTIFIE, None, None, ""
        r.save()
        journaliser(request, JournalAudit.Action.DECISION, r, r.projet, {"decision": decision, "motif": motif,
                                                                         "date_revue": r.date_revue.isoformat() if r.date_revue else None,
                                                                         "niveau": r.niveau})
        libelle = {"accepter": "accepté", "clore": "clos", "rouvrir": "rouvert"}[decision]
        notifier(r.projet, auteur=request.user, type_evenement="risque.decision", titre=f"Risque {libelle} : {r.intitule}",
                 message=motif or f"Décision : risque {libelle}.", lien=lien(r.projet, "risques", r),
                 destinataires=acteurs_concernes(r.projet, responsable=r.proprietaire))
        return Response(RisqueSerializer(r, context={"request": request}).data)


class DerogationViewSet(ProjetScopedViewSet):
    """`?projet=`, `?statut=`. Les dérogations acceptées arrivées à expiration passent « expirées »."""

    queryset = Derogation.objects.select_related("mesure__referentiel", "risque", "demandee_par", "decidee_par")
    serializer_class = DerogationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        expirer_derogations(projets=qs.values("projet").distinct())
        if statut := self.request.query_params.get("statut"):
            qs = qs.filter(statut__in=statut.split(","))
        return qs.order_by("-cree_le")

    def perform_create(self, serializer):
        serializer.validated_data["demandee_par"] = self.request.user
        super().perform_create(serializer)
        d = serializer.instance
        notifier(d.projet, auteur=self.request.user, type_evenement="derogation.demandee", titre="Dérogation demandée",
                 message=d.motif[:1000], lien=lien(d.projet, "derogations", d),
                 destinataires=acteurs_concernes(d.projet, roles=DECISIONNAIRES))

    def perform_destroy(self, instance):
        if instance.statut != Derogation.Statut.DEMANDEE:
            raise PermissionDenied("Une dérogation décidée ne se supprime pas : elle fait partie de l'historique.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"], serializer_class=DecisionDerogationSerializer)
    @transaction.atomic
    def decider(self, request, pk=None):
        d = self.get_object()
        if not peut_decider_projet(request.user, d.projet):
            raise PermissionDenied("Seuls le RSSI, l'autorité d'homologation ou l'administrateur décident.")
        dec = DecisionDerogationSerializer(data=request.data)
        dec.is_valid(raise_exception=True)
        decision, commentaire = dec.validated_data["decision"], dec.validated_data.get("commentaire", "")
        attendu = Derogation.Statut.ACCEPTEE if decision == "revoquer" else Derogation.Statut.DEMANDEE
        if d.statut != attendu:
            return Response({"detail": "Cette décision n'est pas possible dans l'état actuel de la dérogation."},
                            status=status.HTTP_409_CONFLICT)
        if decision == "accepter":
            expiration = dec.validated_data.get("date_expiration") or d.date_expiration
            if not expiration or expiration <= date.today():
                raise serializers.ValidationError({"date_expiration": "Une dérogation acceptée a une date d'expiration future."})
            d.statut, d.date_expiration = Derogation.Statut.ACCEPTEE, expiration
        elif decision == "refuser":
            if not commentaire.strip():
                raise serializers.ValidationError({"commentaire": "Motivez le refus."})
            d.statut = Derogation.Statut.REFUSEE
        else:  # révocation : la dérogation cesse aujourd'hui
            d.statut, d.date_expiration = Derogation.Statut.EXPIREE, date.today()
        if decision != "revoquer":
            d.decidee_par, d.date_decision = request.user, date.today()
        d.commentaire_decision = commentaire
        d.save()
        journaliser(request, JournalAudit.Action.DECISION, d, d.projet, {
            "decision": decision, "commentaire": commentaire, "date_expiration": d.date_expiration.isoformat() if d.date_expiration else None})
        libelle = {"accepter": "acceptée", "refuser": "refusée", "revoquer": "révoquée"}[decision]
        notifier(d.projet, auteur=request.user, type_evenement="derogation.decision", titre=f"Dérogation {libelle}",
                 message=commentaire or d.motif[:500], lien=lien(d.projet, "derogations", d),
                 destinataires=acteurs_concernes(d.projet, en_plus=[d.demandee_par]))
        return Response(DerogationSerializer(d, context={"request": request}).data)
