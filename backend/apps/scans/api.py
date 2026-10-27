"""API des rapports de scan. Dépôt contrôlé comme toute pièce (type réel, taille, nom régénéré, SHA-256), lecture
immédiate, constats consultables et qualifiables, création des tâches sur demande explicite."""

from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.core.api.acces import peut_decider_projet, peut_ecrire_projet
from apps.core.api.base import NomField, ProjetScopedSerializer, ProjetScopedViewSet
from apps.core.api.journal import journaliser
from apps.documents.validation import controler
from apps.suivi.api import signaler_nouvelle_tache

from .analyseurs import SEVERITES, RapportIllisible
from .models import ConstatScan, ImportScan
from .services import creer_taches, traiter


class ImportSerializer(ProjetScopedSerializer):
    fichier = serializers.FileField(write_only=True)
    depose_par_nom = NomField(source="depose_par")
    outil_libelle = serializers.CharField(source="get_outil_display", read_only=True)

    class Meta:
        model = ImportScan
        fields = ["id", "projet", "fichier", "outil", "outil_libelle", "nom_original", "type_mime", "taille", "sha256", "date_scan", "etat",
                  "erreur", "bilan", "depose_par_nom", "depose_le"]
        read_only_fields = ["outil", "nom_original", "type_mime", "taille", "sha256", "date_scan", "etat", "erreur", "bilan", "depose_le"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        controle = controler(attrs["fichier"], attrs["fichier"].name)
        if controle.type_mime not in ("application/xml", "text/csv"):
            raise serializers.ValidationError({"fichier": "Rapport attendu : .nessus ou .xml (Nessus, OpenVAS), ou .csv (Cyberwatch…)."})
        attrs.update(nom_original=attrs["fichier"].name[:255], type_mime=controle.type_mime, taille=controle.taille, sha256=controle.sha256,
                     outil=ImportScan.Outil.CYBERWATCH if controle.type_mime == "text/csv" else ImportScan.Outil.NESSUS)
        attrs["fichier"].name = f"scan{controle.extension}"
        return attrs


class ConstatSerializer(serializers.ModelSerializer):
    statut_par_nom = NomField(source="statut_par")
    a_une_tache = serializers.SerializerMethodField()

    class Meta:
        model = ConstatScan
        fields = ["id", "projet", "import_scan", "identifiant_outil", "titre", "severite", "cvss", "cve", "hote", "port", "protocole",
                  "description", "solution", "statut", "commentaire_statut", "statut_par_nom", "statut_le", "a_une_tache"]
        read_only_fields = fields

    def get_a_une_tache(self, obj) -> bool:
        return obj.identifiant_outil in self.context.get("avec_tache", set())


class StatutConstatSerializer(serializers.Serializer):
    statut = serializers.ChoiceField(choices=ConstatScan.Statut.choices)
    commentaire = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    tous_les_hotes = serializers.BooleanField(required=False, default=False)


class CreationTachesSerializer(serializers.Serializer):
    identifiants = serializers.ListField(child=serializers.CharField(max_length=100), required=False, max_length=500)
    severite_min = serializers.ChoiceField(choices=SEVERITES[1:], required=False)


class ImportViewSet(ProjetScopedViewSet):
    """Rapports de scan d'un projet (`?projet=`). Pas de modification ni de suppression : la pièce est conservée."""

    queryset = ImportScan.objects.select_related("depose_par")
    serializer_class = ImportSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().order_by("-depose_le")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            imp = serializer.save(depose_par=request.user)
            journaliser(request, JournalAudit.Action.CREATION, imp, imp.projet, {"nom": imp.nom_original, "sha256": imp.sha256})
        try:
            traiter(imp)
        except RapportIllisible as e:
            imp.etat, imp.erreur = ImportScan.Etat.ECHEC, str(e)
            imp.save(update_fields=["etat", "erreur"])
            return Response({**ImportSerializer(imp, context={"request": request}).data, "detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        imp.refresh_from_db()
        return Response(ImportSerializer(imp, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def telecharger(self, request, pk=None):
        imp = self.get_object()
        journaliser(request, JournalAudit.Action.TELECHARGEMENT, imp, imp.projet, {"sha256": imp.sha256})
        reponse = FileResponse(imp.fichier.open("rb"), as_attachment=True, filename=imp.nom_original, content_type=imp.type_mime)
        reponse["X-Content-Type-Options"] = "nosniff"
        reponse["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return reponse

    @action(detail=True, methods=["post"], url_path="creer-taches", serializer_class=CreationTachesSerializer)
    @transaction.atomic
    def creer_taches(self, request, pk=None):
        imp = self.get_object()
        if not peut_ecrire_projet(request.user, imp.projet):
            raise PermissionDenied("Écriture non autorisée sur ce projet.")
        demande = CreationTachesSerializer(data=request.data)
        demande.is_valid(raise_exception=True)
        if "identifiants" not in demande.validated_data and "severite_min" not in demande.validated_data:
            raise serializers.ValidationError("Choisissez des vulnérabilités ou une sévérité minimale.")
        crees = creer_taches(imp, demande.validated_data.get("identifiants"), demande.validated_data.get("severite_min"))
        for t in crees:
            signaler_nouvelle_tache(request, t)
        return Response({"crees": len(crees)}, status=status.HTTP_201_CREATED if crees else status.HTTP_200_OK)


class ConstatViewSet(ProjetScopedViewSet):
    """Constats : `?projet=`, `?import_scan=`, `?severite=`, `?statut=`. Qualification par l'action `statuer` :
    faux positif (motivé) par les membres qui écrivent, risque accepté par les décisionnaires."""

    queryset = ConstatScan.objects.select_related("statut_par")
    serializer_class = ConstatSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("import_scan"):
            qs = qs.filter(import_scan_id=p["import_scan"])
        for champ in ("severite", "statut"):  # valeurs multiples séparées par des virgules
            if p.get(champ):
                qs = qs.filter(**{f"{champ}__in": p[champ].split(",")})
        return qs.order_by("-cvss", "titre", "hote")

    def get_serializer_context(self):
        from apps.suivi.models import Tache
        from apps.suivi.services import TACHES_CLOSES

        contexte = super().get_serializer_context()
        if projet := self.request.query_params.get("projet"):
            contexte["avec_tache"] = set(Tache.objects.filter(projet_id=projet, constat_scan__isnull=False).exclude(statut__in=TACHES_CLOSES)
                                         .values_list("constat_scan__identifiant_outil", flat=True))
        return contexte

    @action(detail=True, methods=["post"], serializer_class=StatutConstatSerializer)
    @transaction.atomic
    def statuer(self, request, pk=None):
        constat = self.get_object()
        d = StatutConstatSerializer(data=request.data)
        d.is_valid(raise_exception=True)
        statut, commentaire = d.validated_data["statut"], d.validated_data.get("commentaire", "").strip()
        if statut == ConstatScan.Statut.ACCEPTE and not peut_decider_projet(request.user, constat.projet):
            raise PermissionDenied("Accepter un risque revient au RSSI, à l'autorité d'homologation ou à l'administrateur.")
        if not peut_ecrire_projet(request.user, constat.projet):
            raise PermissionDenied("Écriture non autorisée sur ce projet.")
        if statut in (ConstatScan.Statut.FAUX_POSITIF, ConstatScan.Statut.ACCEPTE) and not commentaire:
            raise serializers.ValidationError({"commentaire": "Justifiez ce choix."})
        cibles = ConstatScan.objects.filter(import_scan=constat.import_scan, identifiant_outil=constat.identifiant_outil) \
            if d.validated_data["tous_les_hotes"] else ConstatScan.objects.filter(pk=constat.pk)
        n = cibles.update(statut=statut, commentaire_statut=commentaire, statut_par=request.user, statut_le=timezone.now())
        journaliser(request, JournalAudit.Action.DECISION if statut == ConstatScan.Statut.ACCEPTE else JournalAudit.Action.MODIFICATION,
                    constat, constat.projet, {"statut": statut, "commentaire": commentaire, "constats": n, "vulnerabilite": constat.identifiant_outil})
        constat.refresh_from_db()
        return Response({**ConstatSerializer(constat, context=self.get_serializer_context()).data, "modifies": n})
