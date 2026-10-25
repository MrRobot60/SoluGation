from django.db import models

from apps.core.models import FichierModel, ProjetModel


class ImportScan(FichierModel, ProjetModel):
    class Outil(models.TextChoices):
        NESSUS = "nessus", "Nessus"
        OPENVAS = "openvas", "OpenVAS"
        CYBERWATCH = "cyberwatch", "Cyberwatch"

    class Etat(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        TRAITE = "traite", "Traité"
        ECHEC = "echec", "Échec"

    outil = models.CharField(max_length=12, choices=Outil.choices)
    date_scan = models.DateTimeField(null=True, blank=True)
    etat = models.CharField(max_length=12, choices=Etat.choices, default=Etat.EN_ATTENTE)
    erreur = models.TextField(blank=True)

    class Meta:
        verbose_name = "import de scan"
        ordering = ["-depose_le"]


class ConstatScan(ProjetModel):
    class Severite(models.TextChoices):
        INFO = "info", "Information"
        FAIBLE = "faible", "Faible"
        MOYENNE = "moyenne", "Moyenne"
        HAUTE = "haute", "Haute"
        CRITIQUE = "critique", "Critique"

    class Statut(models.TextChoices):
        OUVERT = "ouvert", "Ouvert"
        TRAITE = "traite", "Traité"
        FAUX_POSITIF = "faux_positif", "Faux positif"
        ACCEPTE = "accepte", "Risque accepté"

    import_scan = models.ForeignKey(ImportScan, on_delete=models.CASCADE, related_name="constats")
    identifiant_outil = models.CharField(max_length=100, help_text="ID du plugin / de la NVT.")
    titre = models.CharField(max_length=500)
    severite = models.CharField(max_length=10, choices=Severite.choices)
    cvss = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    cve = models.JSONField(default=list, blank=True)
    hote = models.CharField(max_length=255, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    protocole = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    mesures = models.ManyToManyField("referentiels.Mesure", blank=True, related_name="+")
    statut = models.CharField(max_length=14, choices=Statut.choices, default=Statut.OUVERT)

    champs_meme_projet = ("import_scan",)

    class Meta:
        verbose_name = "constat de scan"
        ordering = ["-cvss"]
