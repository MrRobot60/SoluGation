from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import ProjetModel, TenantModel

MAX_REFERENTIELS_PAR_PROJET = 3


class Projet(TenantModel):
    class TypeBien(models.TextChoices):
        APPLICATION = "application", "Application"
        POSTE_TRAVAIL = "poste_travail", "Poste de travail"
        SYSTEME_INFORMATION = "si", "Système d'information"
        AUTRE = "autre", "Autre"

    class NiveauVise(models.TextChoices):
        ELEMENTAIRE = "elementaire", "Élémentaire"
        STANDARD = "standard", "Standard"
        RENFORCE = "renforce", "Renforcé"

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        EN_COURS = "en_cours", "En cours"
        EN_ATTENTE_DECISION = "en_attente_decision", "En attente de décision"
        HOMOLOGUE = "homologue", "Homologué"
        REFUSE = "refuse", "Refusé"
        ARCHIVE = "archive", "Archivé"

    class Decision(models.TextChoices):
        HOMOLOGATION = "homologation", "Homologation"
        HOMOLOGATION_PROVISOIRE = "provisoire", "Homologation provisoire"
        REFUS = "refus", "Refus"

    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type_bien = models.CharField(max_length=20, choices=TypeBien.choices)
    niveau_vise = models.CharField(max_length=20, choices=NiveauVise.choices)
    statut = models.CharField(max_length=24, choices=Statut.choices, default=Statut.BROUILLON)
    referentiels = models.ManyToManyField("referentiels.Referentiel", through="ProjetReferentiel", related_name="projets")
    ebios_active = models.BooleanField("EBIOS RM activé", default=False)

    # Activés par défaut, modifiables dans les paramètres du projet (pas dans l'assistant de création).
    notifications_actives = models.BooleanField(default=True)
    calendrier_actif = models.BooleanField(default=True)

    # Revue périodique
    periodicite_revue_mois = models.PositiveSmallIntegerField(default=12)
    date_prochaine_revue = models.DateField(null=True, blank=True)
    # Rappels déjà envoyés (pour quelle date de revue) : un rappel par échéance, pas à chaque passage.
    rappel_revue_pour = models.DateField(null=True, blank=True, editable=False)
    rappel_retard_pour = models.DateField(null=True, blank=True, editable=False)

    # Décision d'homologation : toujours humaine, jamais issue de l'IA.
    decision = models.CharField(max_length=20, choices=Decision.choices, blank=True)
    decision_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    date_decision = models.DateField(null=True, blank=True)
    date_fin_validite = models.DateField(null=True, blank=True)

    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="projets_crees")

    class Meta:
        ordering = ["-cree_le"]
        constraints = [
            models.UniqueConstraint(fields=["organisation", "nom"], name="projet_nom_unique_par_organisation"),
            models.CheckConstraint(
                name="projet_decision_tracee",
                condition=models.Q(decision="") | models.Q(decision_par__isnull=False, date_decision__isnull=False),
            ),
        ]

    def __str__(self):
        return self.nom


class ProjetReferentiel(ProjetModel):
    """1 à 3 référentiels par projet. La version est figée par la FK (alerte si `remplace_par`)."""

    referentiel = models.ForeignKey("referentiels.Referentiel", on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["projet", "referentiel"], name="projet_referentiel_unique"),
        ]

    def __str__(self):
        return str(self.referentiel)

    def save(self, *args, **kwargs):
        if self.referentiel.organisation_id not in (None, self.projet.organisation_id):
            raise ValidationError("Référentiel privé d'une autre organisation.")
        if self._state.adding:
            if ProjetReferentiel.objects.filter(projet=self.projet).count() >= MAX_REFERENTIELS_PAR_PROJET:
                raise ValidationError(f"{MAX_REFERENTIELS_PAR_PROJET} référentiels maximum par projet.")
        super().save(*args, **kwargs)


class ActeurProjet(ProjetModel):
    """Acteur du projet : utilisateur de l'organisation, ou contact externe sans compte."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="participations"
    )
    nom = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    organisme = models.CharField(max_length=150, blank=True)
    role = models.ForeignKey(
        "comptes.Role", on_delete=models.PROTECT, related_name="acteurs", limit_choices_to={"portee": "projet"}
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["projet", "utilisateur", "role"], name="acteur_role_unique"),
            models.CheckConstraint(
                name="acteur_utilisateur_ou_email",
                condition=models.Q(utilisateur__isnull=False) | ~models.Q(email=""),
            ),
        ]

    def __str__(self):
        return f"{self.utilisateur or self.nom} ({self.role})"

    def save(self, *args, **kwargs):
        if self.utilisateur_id and self.utilisateur.organisation_id != self.projet.organisation_id:
            raise ValidationError("L'utilisateur n'appartient pas à l'organisation du projet.")
        super().save(*args, **kwargs)


class StatutMesure(ProjetModel):
    """État de conformité d'une mesure dans un projet. Décision humaine : l'IA propose via
    ai.ResultatAnalyseMesure, la validation humaine met à jour ce statut."""

    class Statut(models.TextChoices):
        NON_EVALUE = "non_evalue", "Non évalué"
        CONFORME = "conforme", "Conforme"
        PARTIEL = "partiel", "Partiel"
        MANQUANT = "manquant", "Manquant"
        NON_APPLICABLE = "non_applicable", "Non applicable"

    mesure = models.ForeignKey("referentiels.Mesure", on_delete=models.PROTECT, related_name="statuts")
    statut = models.CharField(max_length=16, choices=Statut.choices, default=Statut.NON_EVALUE)
    justification = models.TextField(blank=True)
    resultat_analyse = models.ForeignKey(
        "ai.ResultatAnalyseMesure", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Proposition IA validée à l'origine de ce statut.",
    )
    evalue_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    evalue_le = models.DateTimeField(null=True, blank=True)

    champs_meme_projet = ("resultat_analyse",)

    class Meta:
        verbose_name_plural = "statuts de mesure"
        constraints = [
            models.UniqueConstraint(fields=["projet", "mesure"], name="statut_mesure_unique"),
        ]

    def __str__(self):
        return f"{self.mesure.identifiant} : {self.get_statut_display()}"


class DocumentAttendu(ProjetModel):
    """Ligne de la checklist générée selon le contexte du projet."""

    class Statut(models.TextChoices):
        ATTENDU = "attendu", "Attendu"
        DEPOSE = "depose", "Déposé"
        VALIDE = "valide", "Validé"
        REFUSE = "refuse", "Refusé"
        NON_APPLICABLE = "non_applicable", "Non applicable"

    class Origine(models.TextChoices):
        GENEREE = "generee", "Générée"
        MANUELLE = "manuelle", "Ajout manuel"

    intitule = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    type_document = models.CharField(max_length=100, blank=True, help_text="ex. PSSI, analyse de risques, dossier d'architecture")
    mesures = models.ManyToManyField("referentiels.Mesure", blank=True, related_name="documents_attendus")
    responsable = models.ForeignKey(ActeurProjet, null=True, blank=True, on_delete=models.PROTECT, related_name="documents_attendus")
    echeance = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=16, choices=Statut.choices, default=Statut.ATTENDU)
    obligatoire = models.BooleanField(default=True)
    origine = models.CharField(max_length=10, choices=Origine.choices, default=Origine.GENEREE)

    champs_meme_projet = ("responsable",)

    class Meta:
        verbose_name_plural = "documents attendus"
        ordering = ["echeance", "intitule"]

    def __str__(self):
        return self.intitule
