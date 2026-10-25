"""Briques communes : identifiants UUID, isolation multi-tenant, validation humaine de l'IA, fichiers hashés."""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def echelle_1_4(verbose_name, **kwargs):
    """Échelle de cotation 1 à 4 (gravité, vraisemblance, EBIOS RM...)."""
    return models.PositiveSmallIntegerField(
        verbose_name, validators=[MinValueValidator(1), MaxValueValidator(4)], **kwargs
    )


class HorodatageModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantQuerySet(models.QuerySet):
    def pour_organisation(self, organisation):
        return self.filter(organisation=organisation)


class TenantModel(HorodatageModel):
    """Toute donnée client porte son organisation : c'est la clé de filtrage de chaque requête."""

    organisation = models.ForeignKey(
        "comptes.Organisation", on_delete=models.PROTECT, related_name="+", editable=False
    )

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True


class ProjetModel(TenantModel):
    """Donnée rattachée à un projet. L'organisation est recopiée depuis le projet (dénormalisée
    pour un filtrage simple) et les FK listées dans `champs_meme_projet` doivent pointer vers le
    même projet : impossible de lier un objet d'un autre projet, donc d'une autre organisation."""

    projet = models.ForeignKey("projets.Projet", on_delete=models.PROTECT)

    champs_meme_projet: tuple[str, ...] = ()

    class Meta:
        abstract = True

    def verifier_coherence_projet(self):
        for nom in self.champs_meme_projet:
            cible = getattr(self, nom)
            if cible is not None and cible.projet_id != self.projet_id:
                raise ValidationError({nom: "Objet rattaché à un autre projet."})

    def clean(self):
        super().clean()
        if self.projet_id:
            self.verifier_coherence_projet()

    def save(self, *args, **kwargs):
        self.organisation_id = self.projet.organisation_id
        self.verifier_coherence_projet()
        super().save(*args, **kwargs)


class StatutValidation(models.TextChoices):
    A_VALIDER = "a_valider", "À valider"
    VALIDE = "valide", "Validé"
    REJETE = "rejete", "Rejeté"


class ValidationHumaineModel(models.Model):
    """Règle d'or : l'IA recommande, l'humain valide. Toute conclusion IA naît `a_valider`."""

    statut_validation = models.CharField(
        max_length=12, choices=StatutValidation.choices, default=StatutValidation.A_VALIDER
    )
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    valide_le = models.DateTimeField(null=True, blank=True)
    commentaire_validation = models.TextField(blank=True)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_validation_tracee",
                condition=models.Q(statut_validation=StatutValidation.A_VALIDER)
                | models.Q(valide_par__isnull=False, valide_le__isnull=False),
            ),
        ]

    def _decider(self, statut, utilisateur, commentaire):
        self.statut_validation = statut
        self.valide_par = utilisateur
        self.valide_le = timezone.now()
        self.commentaire_validation = commentaire
        self.save(update_fields=["statut_validation", "valide_par", "valide_le", "commentaire_validation"])

    def valider(self, utilisateur, commentaire=""):
        self._decider(StatutValidation.VALIDE, utilisateur, commentaire)

    def rejeter(self, utilisateur, commentaire=""):
        self._decider(StatutValidation.REJETE, utilisateur, commentaire)


def chemin_fichier(instance, filename):
    """Nom régénéré (UUID), préfixe isolé par organisation. Le nom d'origine est gardé en base."""
    extension = Path(filename).suffix.lower()[:10]
    return f"org/{instance.organisation_id}/{instance._meta.model_name}/{uuid.uuid4().hex}{extension}"


class FichierModel(models.Model):
    """Fichier stocké en S3, hashé SHA-256 à l'enregistrement et immuable ensuite.
    Une nouvelle version = un nouvel enregistrement."""

    fichier = models.FileField(upload_to=chemin_fichier, max_length=255)
    nom_original = models.CharField(max_length=255)
    type_mime = models.CharField(max_length=100)
    taille = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    depose_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    depose_le = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            origine = type(self).objects.filter(pk=self.pk).values("fichier", "sha256").first()
            if origine and (origine["fichier"] != self.fichier.name or origine["sha256"] != self.sha256):
                raise ValidationError("Un fichier déposé est immuable : créer une nouvelle version.")
        super().save(*args, **kwargs)
