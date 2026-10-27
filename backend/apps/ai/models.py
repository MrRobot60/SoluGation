"""Traçabilité des appels IA. Chaque conclusion est stockée `a_valider` : rien n'est décidé par l'IA."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import ProjetModel, ValidationHumaineModel


class AnalyseIA(ValidationHumaineModel, ProjetModel):
    class Type(models.TextChoices):
        ANALYSE_DOCUMENTAIRE = "analyse_documentaire", "Analyse documentaire"
        RECOMMANDATION = "recommandation", "Recommandations"
        REDACTION_RAPPORT = "redaction_rapport", "Rédaction de rapport"
        ANALYSE_SCAN = "analyse_scan", "Analyse de rapport de scan"
        SUGGESTION_EBIOS = "suggestion_ebios", "Propositions EBIOS RM"

    class Etat(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ECHEC = "echec", "Échec"

    type_analyse = models.CharField(max_length=24, choices=Type.choices)
    etat = models.CharField(max_length=12, choices=Etat.choices, default=Etat.EN_ATTENTE)
    documents = models.ManyToManyField("documents.DocumentDepose", blank=True, related_name="analyses")
    fournisseur = models.CharField(max_length=50, help_text="ex. mistral")
    modele = models.CharField(max_length=100)
    version_prompt = models.CharField(max_length=50)
    parametres = models.JSONField(default=dict, blank=True)
    resultat_brut = models.JSONField(null=True, blank=True)
    erreur = models.TextField(blank=True)
    jetons_entree = models.PositiveIntegerField(null=True, blank=True)
    jetons_sortie = models.PositiveIntegerField(null=True, blank=True)
    demandee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    debut_le = models.DateTimeField(null=True, blank=True)
    fin_le = models.DateTimeField(null=True, blank=True)

    class Meta(ValidationHumaineModel.Meta):
        verbose_name = "analyse IA"
        verbose_name_plural = "analyses IA"
        ordering = ["-cree_le"]

    def save(self, *args, **kwargs):
        if self._state.adding and not self.projet.organisation.ia_activee:
            raise ValidationError("L'IA est désactivée pour cette organisation.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_type_analyse_display()} ({self.fournisseur})"


class ResultatAnalyseMesure(ValidationHumaineModel, ProjetModel):
    """Couverture d'une mesure constatée par l'IA dans les documents."""

    class Couverture(models.TextChoices):
        COUVERT = "couvert", "Couvert"
        PARTIEL = "partiel", "Partiel"
        ABSENT = "absent", "Absent"

    analyse = models.ForeignKey(AnalyseIA, on_delete=models.CASCADE, related_name="resultats")
    mesure = models.ForeignKey("referentiels.Mesure", on_delete=models.PROTECT, related_name="+")
    document = models.ForeignKey("documents.DocumentDepose", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    couverture = models.CharField(max_length=10, choices=Couverture.choices)
    justification = models.TextField()
    extraits = models.JSONField(default=list, blank=True, help_text="Passages cités : [{page, texte}].")
    confiance = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    champs_meme_projet = ("analyse", "document")

    class Meta(ValidationHumaineModel.Meta):
        verbose_name = "résultat d'analyse par mesure"
        constraints = ValidationHumaineModel.Meta.constraints + [
            models.UniqueConstraint(fields=["analyse", "mesure", "document"], name="resultat_unique", nulls_distinct=False),
        ]

    def __str__(self):
        return f"{self.mesure.identifiant} : {self.get_couverture_display()}"


class RecommandationIA(ValidationHumaineModel, ProjetModel):
    analyse = models.ForeignKey(AnalyseIA, on_delete=models.CASCADE, related_name="recommandations")
    resultat = models.ForeignKey(ResultatAnalyseMesure, null=True, blank=True, on_delete=models.CASCADE, related_name="recommandations")
    tache = models.ForeignKey("suivi.Tache", null=True, blank=True, on_delete=models.SET_NULL, related_name="recommandations")
    mesure = models.ForeignKey("referentiels.Mesure", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    texte = models.TextField(help_text="Synthèse de la recommandation.")
    etapes = models.JSONField(default=list, blank=True, help_text="Actions concrètes, dans l'ordre.")
    preuve_suggeree = models.TextField(blank=True, help_text="Preuve qui permettrait de clore le manquement.")
    effort = models.CharField(max_length=10, blank=True, choices=[("faible", "Faible"), ("moyen", "Moyen"), ("eleve", "Élevé")])

    champs_meme_projet = ("analyse", "resultat", "tache")

    class Meta(ValidationHumaineModel.Meta):
        verbose_name = "recommandation IA"
        verbose_name_plural = "recommandations IA"

    def __str__(self):
        return self.texte[:80]


class ConfigurationIA(models.Model):
    """Fournisseur d'IA de l'installation, saisi par son administrateur (prime sur le fichier `.env`).
    Une seule ligne. La clé d'API est chiffrée (voir ai/securite.py) et n'est jamais renvoyée au navigateur."""

    instance = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    actif = models.BooleanField(default=False)
    nom = models.CharField(max_length=60, blank=True, help_text="Nom affiché et journalisé, ex. « Scaleway », « Ollama interne ».")
    url = models.URLField(max_length=300, blank=True, help_text="Adresse de l'API compatible OpenAI, ex. https://api.exemple.eu/v1")
    modele = models.CharField(max_length=120, blank=True)
    cle_chiffree = models.TextField(blank=True)
    cle_fin = models.CharField(max_length=4, blank=True, help_text="Quatre derniers caractères, pour reconnaître la clé.")
    responsabilite_acceptee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    responsabilite_acceptee_le = models.DateTimeField(null=True, blank=True)
    modifie_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuration de l'IA"
        verbose_name_plural = "configuration de l'IA"

    @classmethod
    def courante(cls):
        return cls.objects.filter(instance=1).first()

    def __str__(self):
        return f"IA de l'installation : {self.nom or 'aucun fournisseur'}"
