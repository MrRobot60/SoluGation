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
from apps.projets.models import DocumentAttendu

from .models import DocumentDepose
from .validation import controler


class DocumentDeposeSerializer(ProjetScopedSerializer):
    fichier = serializers.FileField(write_only=True)

    class Meta:
        model = DocumentDepose
        fields = ["id", "projet", "document_attendu", "version", "fichier", "nom_original", "type_mime", "taille",
                  "sha256", "depose_par", "depose_le", "commentaire"]
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
            if doc_attendu.statut == DocumentAttendu.Statut.ATTENDU:
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
        qs = DocumentDepose.objects.filter(projet__in=projets_accessibles(self.request.user))
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
