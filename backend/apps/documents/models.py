import uuid

from django.db import models

from apps.core.models import FichierModel, ProjetModel


class DocumentDepose(FichierModel, ProjetModel):
    """Version d'un document déposé en réponse à un DocumentAttendu (ou dépôt libre)."""

    document_attendu = models.ForeignKey(
        "projets.DocumentAttendu", null=True, blank=True, on_delete=models.PROTECT, related_name="versions"
    )
    version = models.PositiveIntegerField(default=1)
    commentaire = models.TextField(blank=True)

    champs_meme_projet = ("document_attendu",)

    class Meta:
        verbose_name_plural = "documents déposés"
        ordering = ["document_attendu", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["document_attendu", "version"], name="document_version_unique"),
        ]

    def __str__(self):
        return f"{self.nom_original} v{self.version}"


class Preuve(FichierModel, ProjetModel):
    """Coffre de preuves versionné : toutes les versions d'une même preuve partagent `serie`."""

    serie = models.UUIDField(default=uuid.uuid4, db_index=True)
    version = models.PositiveIntegerField(default=1)
    titre = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    mesures = models.ManyToManyField("referentiels.Mesure", blank=True, related_name="preuves")
    tache = models.ForeignKey("suivi.Tache", null=True, blank=True, on_delete=models.PROTECT, related_name="preuves")
    date_validite = models.DateField(null=True, blank=True, help_text="Date au-delà de laquelle la preuve doit être renouvelée.")

    champs_meme_projet = ("tache",)

    class Meta:
        ordering = ["serie", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["serie", "version"], name="preuve_version_unique"),
        ]

    def __str__(self):
        return f"{self.titre} v{self.version}"
