"""EBIOS Risk Manager (ANSSI) : ateliers 1 à 5. Méthode optionnelle, activable par projet."""

from django.db import models

from apps.core.models import ProjetModel, ValidationHumaineModel, echelle_1_4


class AtelierEBIOS(ProjetModel):
    class Numero(models.IntegerChoices):
        CADRAGE_SOCLE = 1, "1 — Cadrage et socle de sécurité"
        SOURCES_RISQUE = 2, "2 — Sources de risque"
        SCENARIOS_STRATEGIQUES = 3, "3 — Scénarios stratégiques"
        SCENARIOS_OPERATIONNELS = 4, "4 — Scénarios opérationnels"
        TRAITEMENT = 5, "5 — Traitement du risque"

    class Statut(models.TextChoices):
        NON_COMMENCE = "non_commence", "Non commencé"
        EN_COURS = "en_cours", "En cours"
        TERMINE = "termine", "Terminé"

    numero = models.PositiveSmallIntegerField(choices=Numero.choices)
    statut = models.CharField(max_length=14, choices=Statut.choices, default=Statut.NON_COMMENCE)
    notes = models.TextField(blank=True)
    participants = models.ManyToManyField("projets.ActeurProjet", blank=True, related_name="ateliers_ebios")
    date_atelier = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "atelier EBIOS RM"
        verbose_name_plural = "ateliers EBIOS RM"
        ordering = ["projet", "numero"]
        constraints = [
            models.UniqueConstraint(fields=["projet", "numero"], name="atelier_unique"),
        ]


# --- Atelier 1 : cadrage et socle de sécurité ---------------------------------------------

    def __str__(self):
        return self.get_numero_display()


class ValeurMetier(ProjetModel):
    class Nature(models.TextChoices):
        PROCESSUS = "processus", "Processus"
        INFORMATION = "information", "Information"

    nom = models.CharField(max_length=200)
    nature = models.CharField(max_length=12, choices=Nature.choices)
    description = models.TextField(blank=True)
    entite_responsable = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "valeur métier"

    def __str__(self):
        return self.nom


class BienSupport(ProjetModel):
    nom = models.CharField(max_length=200)
    type_bien = models.CharField(max_length=100, blank=True, help_text="ex. serveur, application, réseau, personne, local")
    description = models.TextField(blank=True)
    valeurs_metier = models.ManyToManyField(ValeurMetier, blank=True, related_name="biens_supports")
    entite_responsable = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.nom


class EvenementRedoute(ProjetModel):
    valeur_metier = models.ForeignKey(ValeurMetier, on_delete=models.CASCADE, related_name="evenements_redoutes")
    description = models.TextField()
    impacts = models.TextField(blank=True)
    gravite = echelle_1_4("gravité")

    champs_meme_projet = ("valeur_metier",)

    class Meta:
        verbose_name = "événement redouté"

    def __str__(self):
        return self.description[:80]


class EcartSocle(ProjetModel):
    """Écart constaté au socle de sécurité (référentiels applicables du projet)."""

    class Etat(models.TextChoices):
        APPLIQUE = "applique", "Appliqué sans restriction"
        RESTRICTIONS = "restrictions", "Appliqué avec restrictions"
        NON_APPLIQUE = "non_applique", "Non appliqué"

    referentiel = models.ForeignKey("referentiels.Referentiel", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    mesure = models.ForeignKey("referentiels.Mesure", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    intitule = models.CharField(max_length=300)
    etat = models.CharField(max_length=14, choices=Etat.choices)
    justification = models.TextField(blank=True)

    class Meta:
        verbose_name = "écart au socle"


# --- Atelier 2 : sources de risque ---------------------------------------------------------

    def __str__(self):
        return self.intitule


class SourceRisque(ProjetModel):
    libelle = models.CharField(max_length=200)
    categorie = models.CharField(max_length=100, blank=True, help_text="ex. État, crime organisé, hacktiviste, interne")
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "source de risque"

    def __str__(self):
        return self.libelle


class ObjectifVise(ProjetModel):
    libelle = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "objectif visé"

    def __str__(self):
        return self.libelle


class CoupleSROV(ProjetModel):
    source = models.ForeignKey(SourceRisque, on_delete=models.CASCADE, related_name="couples")
    objectif = models.ForeignKey(ObjectifVise, on_delete=models.CASCADE, related_name="couples")
    motivation = echelle_1_4("motivation")
    ressources = echelle_1_4("ressources")
    activite = echelle_1_4("activité")
    pertinence = echelle_1_4("pertinence")
    retenu = models.BooleanField(default=False)
    justification = models.TextField(blank=True)

    champs_meme_projet = ("source", "objectif")

    class Meta:
        verbose_name = "couple SR/OV"
        verbose_name_plural = "couples SR/OV"
        constraints = [
            models.UniqueConstraint(fields=["source", "objectif"], name="couple_srov_unique"),
        ]


# --- Atelier 3 : scénarios stratégiques ----------------------------------------------------

    def __str__(self):
        return f"{self.source} → {self.objectif}"


class PartiePrenante(ProjetModel):
    nom = models.CharField(max_length=200)
    categorie = models.CharField(max_length=100, blank=True, help_text="ex. fournisseur, prestataire, partenaire, client")
    dependance = echelle_1_4("dépendance")
    penetration = echelle_1_4("pénétration")
    maturite = echelle_1_4("maturité cyber")
    confiance = echelle_1_4("confiance")
    critique = models.BooleanField(default=False)

    class Meta:
        verbose_name = "partie prenante"

    def __str__(self):
        return self.nom

    @property
    def niveau_menace(self):
        return round((self.dependance * self.penetration) / (self.maturite * self.confiance), 2)


class ScenarioStrategique(ProjetModel):
    couple = models.ForeignKey(CoupleSROV, on_delete=models.CASCADE, related_name="scenarios")
    intitule = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    evenements_redoutes = models.ManyToManyField(EvenementRedoute, blank=True, related_name="scenarios")
    gravite = echelle_1_4("gravité")

    champs_meme_projet = ("couple",)

    class Meta:
        verbose_name = "scénario stratégique"

    def __str__(self):
        return self.intitule


class CheminAttaque(ProjetModel):
    scenario = models.ForeignKey(ScenarioStrategique, on_delete=models.CASCADE, related_name="chemins")
    description = models.TextField()
    parties_prenantes = models.ManyToManyField(PartiePrenante, blank=True, related_name="chemins")

    champs_meme_projet = ("scenario",)

    class Meta:
        verbose_name = "chemin d'attaque"

    def __str__(self):
        return self.description[:80]


class MesureEcosysteme(ProjetModel):
    partie_prenante = models.ForeignKey(PartiePrenante, on_delete=models.CASCADE, related_name="mesures")
    intitule = models.CharField(max_length=300)
    description = models.TextField(blank=True)

    champs_meme_projet = ("partie_prenante",)

    class Meta:
        verbose_name = "mesure sur l'écosystème"


# --- Atelier 4 : scénarios opérationnels ---------------------------------------------------

    def __str__(self):
        return self.intitule


class ScenarioOperationnel(ProjetModel):
    chemin = models.ForeignKey(CheminAttaque, on_delete=models.CASCADE, related_name="scenarios_operationnels")
    intitule = models.CharField(max_length=300)
    mode_operatoire = models.TextField(blank=True)
    biens_supports = models.ManyToManyField(BienSupport, blank=True, related_name="scenarios_operationnels")
    vraisemblance = echelle_1_4("vraisemblance")

    champs_meme_projet = ("chemin",)

    class Meta:
        verbose_name = "scénario opérationnel"

    def __str__(self):
        return self.intitule


# --- Atelier 5 : traitement du risque ------------------------------------------------------


class RisqueEBIOS(ProjetModel):
    class Option(models.TextChoices):
        REDUIRE = "reduire", "Réduire"
        TRANSFERER = "transferer", "Transférer"
        EVITER = "eviter", "Éviter"
        ACCEPTER = "accepter", "Accepter"

    scenario_strategique = models.ForeignKey(ScenarioStrategique, on_delete=models.PROTECT, related_name="risques")
    scenario_operationnel = models.ForeignKey(
        ScenarioOperationnel, null=True, blank=True, on_delete=models.PROTECT, related_name="risques"
    )
    intitule = models.CharField(max_length=300)
    gravite = echelle_1_4("gravité initiale")
    vraisemblance = echelle_1_4("vraisemblance initiale")
    option_traitement = models.CharField(max_length=12, choices=Option.choices, blank=True)
    gravite_residuelle = echelle_1_4("gravité résiduelle", null=True, blank=True)
    vraisemblance_residuelle = echelle_1_4("vraisemblance résiduelle", null=True, blank=True)

    champs_meme_projet = ("scenario_strategique", "scenario_operationnel")

    class Meta:
        verbose_name = "risque EBIOS"

    def __str__(self):
        return self.intitule


class MesureTraitement(ProjetModel):
    """Mesure du PACS (plan d'amélioration continue de la sécurité)."""

    intitule = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    risques = models.ManyToManyField(RisqueEBIOS, blank=True, related_name="mesures_traitement")
    responsable = models.ForeignKey("projets.ActeurProjet", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    echeance = models.DateField(null=True, blank=True)
    freins = models.TextField(blank=True)
    cout_complexite = echelle_1_4("coût / complexité", null=True, blank=True)
    tache = models.ForeignKey("suivi.Tache", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    champs_meme_projet = ("responsable", "tache")

    class Meta:
        verbose_name = "mesure de traitement (PACS)"


# --- Propositions de l'IA (ateliers 1 à 4) ---------------------------------------------------

    def __str__(self):
        return self.intitule


class SuggestionEBIOS(ValidationHumaineModel, ProjetModel):
    """Proposition de l'IA, à valider : acceptée (éventuellement corrigée), elle crée les objets de l'atelier."""

    class TypeObjet(models.TextChoices):
        EVENEMENT_REDOUTE = "evenement_redoute", "Événement redouté"
        BIEN_SUPPORT = "bien_support", "Bien support"
        COUPLE = "couple", "Couple source de risque / objectif visé"
        SCENARIO_STRATEGIQUE = "scenario_strategique", "Scénario stratégique et chemins d'attaque"
        SCENARIO_OPERATIONNEL = "scenario_operationnel", "Scénario opérationnel"

    analyse = models.ForeignKey("ai.AnalyseIA", on_delete=models.CASCADE, related_name="suggestions_ebios")
    atelier = models.PositiveSmallIntegerField(choices=AtelierEBIOS.Numero.choices)
    type_objet = models.CharField(max_length=24, choices=TypeObjet.choices)
    parent_id = models.UUIDField(null=True, blank=True, help_text="Valeur métier, couple SR/OV ou chemin d'attaque visé.")
    contenu = models.JSONField(default=dict)
    objets_crees = models.JSONField(default=list, blank=True, help_text="[{type, id}] créés à l'acceptation.")

    champs_meme_projet = ("analyse",)

    class Meta(ValidationHumaineModel.Meta):
        verbose_name = "proposition EBIOS RM de l'IA"
        verbose_name_plural = "propositions EBIOS RM de l'IA"
        ordering = ["atelier", "cree_le"]

    def __str__(self):
        return f"{self.get_type_objet_display()} (atelier {self.atelier})"
