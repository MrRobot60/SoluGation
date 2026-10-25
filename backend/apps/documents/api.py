from django.db import transaction
from django.db.models import Max
from django.http import FileResponse
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser

from apps.audit.models import JournalAudit
from apps.core.api.acces import projets_accessibles
from apps.core.api.base import ProjetScopedSerializer
from apps.core.api.journal import journaliser
from apps.core.api.permissions import EcritureSelonRole, MembreOrganisation
from apps.projets.models import DocumentAttendu, Projet
from apps.referentiels.models import Mesure

from .models import DocumentDepose, Preuve
from .validation import controler


class DocumentDeposeSerializer(ProjetScopedSerializer):
    fichier = serializers.FileField(write_only=True)
    depose_par_nom = serializers.CharField(source="depose_par.__str__", read_only=True)

    class Meta:
        model = DocumentDepose
        fields = ["id", "projet", "document_attendu", "version", "fichier", "nom_original", "type_mime", "taille",
                  "sha256", "depose_par", "depose_par_nom", "depose_le", "commentaire"]
        read_only_fields = ["version", "nom_original", "type_mime", "taille", "sha256", "depose_par", "depose_le"]
        # La version est calculée sous verrou dans create() ; l'unicité reste garantie par la contrainte en base.
        validators = []

    def validate(self, attrs):
        attrs = super().validate(attrs)
        controle = controler(attrs["fichier"], attrs["fichier"].name)
        attrs.update(
            nom_original=attrs["fichier"].name[:255], type_mime=controle.type_mime, taille=controle.taille,
            sha256=controle.sha256,
        )
        # Nom de stockage : seule l'extension du type détecté est conservée (chemin_fichier régénère le reste).
        attrs["fichier"].name = f"depot{controle.extension}"
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        doc_attendu = validated_data.get("document_attendu")
        version = 1
        if doc_attendu is not None:
            DocumentAttendu.objects.select_for_update().filter(pk=doc_attendu.pk).first()  # versions séquentielles
            version = (DocumentDepose.objects.filter(document_attendu=doc_attendu).aggregate(m=Max("version"))["m"] or 0) + 1
            # Première version, ou nouvelle version après un refus : la pièce repasse en relecture.
            if doc_attendu.statut in (DocumentAttendu.Statut.ATTENDU, DocumentAttendu.Statut.REFUSE):
                doc_attendu.statut = DocumentAttendu.Statut.DEPOSE
                doc_attendu.save(update_fields=["statut", "modifie_le"])
        return DocumentDepose.objects.create(version=version, depose_par=self.context["request"].user, **validated_data)


class DocumentDeposeViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                            viewsets.GenericViewSet):
    """Dépôt (multipart) et consultation. Ni modification ni suppression : une correction = une nouvelle version.
    `?projet=` / `?document_attendu=` pour filtrer."""

    serializer_class = DocumentDeposeSerializer
    permission_classes = [MembreOrganisation, EcritureSelonRole]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = DocumentDepose.objects.filter(projet__in=projets_accessibles(self.request.user)).select_related("depose_par")
        p = self.request.query_params
        if p.get("projet"):
            qs = qs.filter(projet_id=p["projet"])
        if p.get("document_attendu"):
            qs = qs.filter(document_attendu_id=p["document_attendu"])
        return qs

    def perform_create(self, serializer):
        doc = serializer.save()
        journaliser(self.request, JournalAudit.Action.CREATION, doc, doc.projet,
                    {"nom_original": doc.nom_original, "version": doc.version, "sha256": doc.sha256, "taille": doc.taille})

    @action(detail=True, methods=["get"])
    def telecharger(self, request, pk=None):
        """Flux servi par le backend (le stockage S3 n'est jamais exposé au navigateur), tracé au journal."""
        doc = self.get_object()
        journaliser(request, JournalAudit.Action.TELECHARGEMENT, doc, doc.projet, {"sha256": doc.sha256})
        reponse = FileResponse(doc.fichier.open("rb"), as_attachment=True, filename=doc.nom_original,
                               content_type=doc.type_mime)
        reponse["X-Content-Type-Options"] = "nosniff"
        reponse["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return reponse


class PreuveSerializer(ProjetScopedSerializer):
    """Coffre de preuves : `serie` absente = nouvelle preuve (v1) ; `serie` d'une preuve existante = version suivante."""

    fichier = serializers.FileField(write_only=True)
    serie = serializers.UUIDField(required=False)
    mesures = serializers.PrimaryKeyRelatedField(many=True, queryset=Mesure.objects.all())
    depose_par_nom = serializers.CharField(source="depose_par.__str__", read_only=True)

    class Meta:
        model = Preuve
        fields = ["id", "projet", "serie", "version", "titre", "description", "mesures", "tache", "date_validite",
                  "fichier", "nom_original", "type_mime", "taille", "sha256", "depose_par", "depose_par_nom", "depose_le"]
        read_only_fields = ["version", "nom_original", "type_mime", "taille", "sha256", "depose_par", "depose_le"]
        validators = []  # version calculée sous verrou ; unicité garantie en base

    def validate(self, attrs):
        attrs = super().validate(attrs)
        projet = attrs["projet"]
        refs = set(projet.referentiels.values_list("id", flat=True))
        if not attrs["mesures"] or any(m.referentiel_id not in refs for m in attrs["mesures"]):
            raise serializers.ValidationError({"mesures": "Au moins une mesure, parmi les référentiels du projet."})
        if "serie" in attrs and not Preuve.objects.filter(projet=projet, serie=attrs["serie"]).exists():
            raise serializers.ValidationError({"serie": "Preuve inexistante."})
        controle = controler(attrs["fichier"], attrs["fichier"].name)
        attrs.update(nom_original=attrs["fichier"].name[:255], type_mime=controle.type_mime, taille=controle.taille,
                     sha256=controle.sha256)
        attrs["fichier"].name = f"preuve{controle.extension}"
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        mesures = validated_data.pop("mesures")
        serie = validated_data.get("serie")
        if serie:
            Projet.objects.select_for_update().filter(pk=validated_data["projet"].pk).first()  # versions séquentielles
            validated_data["version"] = (Preuve.objects.filter(serie=serie).aggregate(m=Max("version"))["m"] or 0) + 1
        preuve = Preuve.objects.create(depose_par=self.context["request"].user, **validated_data)
        preuve.mesures.set(mesures)
        return preuve


class PreuveViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Coffre de preuves versionné : ni modification ni suppression. `?projet=`, `?mesure=`, `?serie=`."""

    serializer_class = PreuveSerializer
    permission_classes = [MembreOrganisation, EcritureSelonRole]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = (Preuve.objects.filter(projet__in=projets_accessibles(self.request.user))
              .select_related("depose_par").prefetch_related("mesures").order_by("serie", "-version"))
        p = self.request.query_params
        for champ, filtre in (("projet", "projet_id"), ("mesure", "mesures"), ("serie", "serie")):
            if p.get(champ):
                qs = qs.filter(**{filtre: p[champ]})
        return qs.distinct()

    def perform_create(self, serializer):
        preuve = serializer.save()
        journaliser(self.request, JournalAudit.Action.CREATION, preuve, preuve.projet, {
            "titre": preuve.titre, "version": preuve.version, "sha256": preuve.sha256,
            "mesures": [m.identifiant for m in preuve.mesures.all()],
        })

    @action(detail=True, methods=["get"])
    def telecharger(self, request, pk=None):
        preuve = self.get_object()
        journaliser(request, JournalAudit.Action.TELECHARGEMENT, preuve, preuve.projet, {"sha256": preuve.sha256})
        reponse = FileResponse(preuve.fichier.open("rb"), as_attachment=True, filename=preuve.nom_original,
                               content_type=preuve.type_mime)
        reponse["X-Content-Type-Options"] = "nosniff"
        reponse["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return reponse
