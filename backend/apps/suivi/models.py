from django.conf import settings
from django.db import models

from apps.core.models import ProjetModel, TenantModel


class ActionPlan(ProjetModel):
    titre = models.CharField(max_length=200, default="Plan d'action")

    class Meta:
        verbose_name = "plan d'action"
        constraints = [
            models.UniqueConstraint(fields=["projet"], name="un_plan_par_projet"),
        ]


class Tache(ProjetModel):
    """Un manquement = une tâche (responsable, échéance, preuve attendue)."""

    class Statut(models.TextChoices):
        A_FAIRE = "a_faire", "À faire"
        EN_COURS = "en_cours", "En cours"
        EN_REVUE = "en_revue", "En revue"
        TERMINEE = "terminee", "Terminée"
        ABANDONNEE = "abandonnee", "Abandonnée"

    class Priorite(models.TextChoices):
        BASSE = "basse", "Basse"
        MOYENNE = "moyenne", "Moyenne"
        HAUTE = "haute", "Haute"
        CRITIQUE = "critique", "Critique"

    class Origine(models.TextChoices):
        ANALYSE_IA = "analyse_ia", "Analyse IA"
        SCAN = "scan", "Rapport de scan"
        EBIOS = "ebios", "EBIOS RM"
        MANUELLE = "manuelle", "Manuelle"

    plan = models.ForeignKey(ActionPlan, on_delete=models.CASCADE, related_name="taches")
    titre = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    mesure = models.ForeignKey("referentiels.Mesure", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    resultat_analyse = models.ForeignKey(
        "ai.ResultatAnalyseMesure", null=True, blank=True, on_delete=models.SET_NULL, related_name="taches"
    )
    constat_scan = models.ForeignKey("scans.ConstatScan", null=True, blank=True, on_delete=models.SET_NULL, related_name="taches")
    responsable = models.ForeignKey("projets.ActeurProjet", null=True, blank=True, on_delete=models.PROTECT, related_name="taches")
    echeance = models.DateField(null=True, blank=True)
    preuve_attendue = models.TextField(blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.A_FAIRE)
    priorite = models.CharField(max_length=10, choices=Priorite.choices, default=Priorite.MOYENNE)
    origine = models.CharField(max_length=12, choices=Origine.choices, default=Origine.MANUELLE)
    cloturee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    cloturee_le = models.DateTimeField(null=True, blank=True)

    champs_meme_projet = ("plan", "resultat_analyse", "constat_scan", "responsable")

    class Meta:
        verbose_name = "tâche"
        ordering = ["echeance", "-priorite"]

    def __str__(self):
        return self.titre


class Commentaire(ProjetModel):
    """Commentaire sur exactement un objet (tâche, document attendu, statut de mesure ou risque)."""

    CIBLES = ("tache", "document_attendu", "statut_mesure", "risque")

    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commentaires")
    texte = models.TextField()
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="reponses")
    tache = models.ForeignKey(Tache, null=True, blank=True, on_delete=models.CASCADE, related_name="commentaires")
    document_attendu = models.ForeignKey(
        "projets.DocumentAttendu", null=True, blank=True, on_delete=models.CASCADE, related_name="commentaires"
    )
    statut_mesure = models.ForeignKey(
        "projets.StatutMesure", null=True, blank=True, on_delete=models.CASCADE, related_name="commentaires"
    )
    risque = models.ForeignKey(
        "risques.RisqueResiduel", null=True, blank=True, on_delete=models.CASCADE, related_name="commentaires"
    )
    edite_le = models.DateTimeField(null=True, blank=True)

    champs_meme_projet = ("parent",) + CIBLES

    class Meta:
        ordering = ["cree_le"]
        constraints = [
            models.CheckConstraint(
                name="commentaire_une_seule_cible",
                condition=(
                    models.Q(tache__isnull=False, document_attendu__isnull=True, statut_mesure__isnull=True, risque__isnull=True)
                    | models.Q(tache__isnull=True, document_attendu__isnull=False, statut_mesure__isnull=True, risque__isnull=True)
                    | models.Q(tache__isnull=True, document_attendu__isnull=True, statut_mesure__isnull=False, risque__isnull=True)
                    | models.Q(tache__isnull=True, document_attendu__isnull=True, statut_mesure__isnull=True, risque__isnull=False)
                ),
            ),
        ]


class Reunion(ProjetModel):
    class Statut(models.TextChoices):
        PLANIFIEE = "planifiee", "Planifiée"
        TENUE = "tenue", "Tenue"
        ANNULEE = "annulee", "Annulée"

    titre = models.CharField(max_length=200)
    debut = models.DateTimeField()
    fin = models.DateTimeField()
    lieu = models.CharField(max_length=200, blank=True)
    lien_visio = models.URLField(blank=True)
    participants = models.ManyToManyField("projets.ActeurProjet", blank=True, related_name="reunions")
    ordre_du_jour = models.TextField(blank=True)
    compte_rendu = models.TextField(blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.PLANIFIEE)
    organisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    id_externe = models.CharField(max_length=255, blank=True, help_text="Identifiant Outlook / Microsoft Graph (synchro ultérieure).")

    class Meta:
        verbose_name = "réunion"
        ordering = ["debut"]
        constraints = [
            models.CheckConstraint(name="reunion_fin_apres_debut", condition=models.Q(fin__gt=models.F("debut"))),
        ]


class Notification(TenantModel):
    destinataire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    projet = models.ForeignKey("projets.Projet", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    type_evenement = models.CharField(max_length=50, help_text="ex. tache.modifiee, document.depose, echeance.proche")
    titre = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    lien = models.CharField(max_length=300, blank=True, help_text="Chemin relatif dans l'application.")
    lue_le = models.DateTimeField(null=True, blank=True)
    mail_envoye_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-cree_le"]
        indexes = [models.Index(fields=["destinataire", "lue_le"])]
