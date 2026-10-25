from django.conf import settings
from django.db import models

from apps.core.models import ProjetModel, echelle_1_4


class RisqueResiduel(ProjetModel):
    class Origine(models.TextChoices):
        EBIOS = "ebios", "EBIOS RM"
        ANALYSE = "analyse", "Analyse de conformité"
        SCAN = "scan", "Rapport de scan"
        MANUELLE = "manuelle", "Saisie manuelle"

    class Statut(models.TextChoices):
        IDENTIFIE = "identifie", "Identifié"
        EN_TRAITEMENT = "en_traitement", "En traitement"
        ACCEPTE = "accepte", "Accepté"
        CLOS = "clos", "Clos"

    intitule = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    origine = models.CharField(max_length=10, choices=Origine.choices, default=Origine.MANUELLE)
    risque_ebios = models.ForeignKey("ebios.RisqueEBIOS", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    gravite = echelle_1_4("gravité")
    vraisemblance = echelle_1_4("vraisemblance")
    mesures = models.ManyToManyField("referentiels.Mesure", blank=True, related_name="+")
    proprietaire = models.ForeignKey("projets.ActeurProjet", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    statut = models.CharField(max_length=14, choices=Statut.choices, default=Statut.IDENTIFIE)
    date_revue = models.DateField(null=True, blank=True)

    champs_meme_projet = ("risque_ebios", "proprietaire")

    class Meta:
        verbose_name = "risque résiduel"
        verbose_name_plural = "risques résiduels"
        ordering = ["-gravite", "-vraisemblance"]

    def __str__(self):
        return self.intitule

    @property
    def niveau(self):
        return self.gravite * self.vraisemblance


class Derogation(ProjetModel):
    """Écart accepté sur une mesure ou un risque, avec acceptation datée et nominative."""

    class Statut(models.TextChoices):
        DEMANDEE = "demandee", "Demandée"
        ACCEPTEE = "acceptee", "Acceptée"
        REFUSEE = "refusee", "Refusée"
        EXPIREE = "expiree", "Expirée"

    risque = models.ForeignKey(RisqueResiduel, null=True, blank=True, on_delete=models.PROTECT, related_name="derogations")
    mesure = models.ForeignKey("referentiels.Mesure", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    motif = models.TextField()
    mesures_compensatoires = models.TextField(blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.DEMANDEE)
    demandee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    decidee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    date_decision = models.DateField(null=True, blank=True)
    date_expiration = models.DateField(null=True, blank=True)

    champs_meme_projet = ("risque",)

    class Meta:
        verbose_name = "dérogation"
        constraints = [
            models.CheckConstraint(
                name="derogation_cible", condition=models.Q(risque__isnull=False) | models.Q(mesure__isnull=False)
            ),
            models.CheckConstraint(
                name="derogation_decision_tracee",
                condition=models.Q(statut__in=["demandee"])
                | models.Q(decidee_par__isnull=False, date_decision__isnull=False),
            ),
        ]
