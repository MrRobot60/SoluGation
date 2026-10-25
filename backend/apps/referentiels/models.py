"""Bibliothèque de référentiels. Données génériques : un référentiel = une liste de mesures."""

from django.db import models

from apps.core.models import HorodatageModel


class Licence(models.TextChoices):
    LIBRE = "libre", "Libre / domaine public"
    LICENCE_OUVERTE = "licence_ouverte", "Licence Ouverte Etalab"
    CC_BY_SA = "cc_by_sa", "CC BY-SA"
    PROPRIETAIRE = "proprietaire", "Propriétaire (copie licenciée du client)"


class Referentiel(HorodatageModel):
    """`organisation` vide = bibliothèque commune (sources libres importées par script).
    Renseignée = import privé d'une organisation (copie licenciée, ex. ISO 27001)."""

    organisation = models.ForeignKey(
        "comptes.Organisation", null=True, blank=True, on_delete=models.CASCADE, related_name="referentiels_prives"
    )
    code = models.SlugField(max_length=50, help_text="ex. iso27001, rgs, hygiene-anssi, ii901, nist-csf, owasp-asvs")
    nom = models.CharField(max_length=200)
    version = models.CharField(max_length=30)
    editeur = models.CharField(max_length=100, blank=True)
    url_source = models.URLField(blank=True)
    date_publication = models.DateField(null=True, blank=True)
    date_import = models.DateTimeField(null=True, blank=True)
    empreinte_source = models.CharField("SHA-256 du fichier source importé", max_length=64, blank=True)
    licence = models.CharField(max_length=20, choices=Licence.choices)
    texte_embarque = models.BooleanField(
        default=False, help_text="Faux en version commerciale pour les normes payantes : identifiant + intitulé reformulé seulement."
    )
    remplace_par = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="remplace",
        help_text="Nouvelle version disponible : sert à l'alerte de mise à jour.",
    )
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["code", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "code", "version"], name="referentiel_unique", nulls_distinct=False
            ),
        ]

    def __str__(self):
        return f"{self.nom} ({self.version})"


class Mesure(HorodatageModel):
    referentiel = models.ForeignKey(Referentiel, on_delete=models.CASCADE, related_name="mesures")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="enfants",
        help_text="Chapitre ou section parente (ex. V1 → V1.2 dans ASVS).",
    )
    identifiant = models.CharField(max_length=50, help_text="ex. A.5.1, R12, PR.AA-01, V2.1.1")
    intitule = models.CharField(max_length=500)
    categorie = models.CharField(max_length=200, blank=True)
    texte_officiel = models.TextField(null=True, blank=True)
    licence = models.CharField(max_length=20, choices=Licence.choices, blank=True, help_text="Vide = celle du référentiel.")
    niveaux = models.JSONField(default=list, blank=True, help_text='Niveaux concernés, ex. ["L1", "L2"] ou ["standard", "renforcé"].')
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["referentiel", "ordre", "identifiant"]
        constraints = [
            models.UniqueConstraint(fields=["referentiel", "identifiant"], name="mesure_identifiant_unique"),
        ]

    def __str__(self):
        return f"{self.identifiant} — {self.intitule}"


class CorrespondanceMesure(HorodatageModel):
    """Mesures pivots : une preuve qui couvre la source couvre aussi la cible (selon le type)."""

    class Type(models.TextChoices):
        EQUIVALENTE = "equivalente", "Équivalente"
        PARTIELLE = "partielle", "Partielle"
        INCLUT = "inclut", "La source inclut la cible"

    class Origine(models.TextChoices):
        OFFICIELLE = "officielle", "Table officielle"
        MANUELLE = "manuelle", "Saisie manuelle"

    organisation = models.ForeignKey(
        "comptes.Organisation", null=True, blank=True, on_delete=models.CASCADE, related_name="+",
        help_text="Vide = correspondance commune.",
    )
    mesure_source = models.ForeignKey(Mesure, on_delete=models.CASCADE, related_name="correspondances_sortantes")
    mesure_cible = models.ForeignKey(Mesure, on_delete=models.CASCADE, related_name="correspondances_entrantes")
    type_correspondance = models.CharField(max_length=12, choices=Type.choices)
    origine = models.CharField(max_length=12, choices=Origine.choices)
    reference = models.CharField(max_length=300, blank=True, help_text="Source de la table de correspondance.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "mesure_source", "mesure_cible"], name="correspondance_unique", nulls_distinct=False
            ),
            models.CheckConstraint(
                name="correspondance_pas_reflexive", condition=~models.Q(mesure_source=models.F("mesure_cible"))
            ),
        ]
