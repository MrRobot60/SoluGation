from django.conf import settings
from django.db import models

from apps.core.models import ProjetModel, ValidationHumaineModel, chemin_fichier


class Rapport(ValidationHumaineModel, ProjetModel):
    """Rapport d'état des lieux. Le texte (rédigé par l'IA, validé par un humain) est stocké en base ;
    le PDF est ensuite généré depuis ce texte + `donnees` sans aucun appel IA."""

    version = models.PositiveIntegerField()
    titre = models.CharField(max_length=300)
    sections = models.JSONField(default=list, help_text="[{titre, texte}] rédigées par l'IA puis éditées.")
    donnees = models.JSONField(default=dict, help_text="Instantané des données structurées (sert aussi à comparer deux versions).")
    analyse_ia = models.ForeignKey("ai.AnalyseIA", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    rapport_precedent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    fichier_pdf = models.FileField(upload_to=chemin_fichier, max_length=255, blank=True)
    sha256_pdf = models.CharField(max_length=64, blank=True)
    genere_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    pdf_genere_le = models.DateTimeField(null=True, blank=True)

    champs_meme_projet = ("analyse_ia", "rapport_precedent")

    class Meta(ValidationHumaineModel.Meta):
        ordering = ["projet", "-version"]
        constraints = ValidationHumaineModel.Meta.constraints + [
            models.UniqueConstraint(fields=["projet", "version"], name="rapport_version_unique"),
        ]

    def __str__(self):
        return f"{self.titre} v{self.version}"
