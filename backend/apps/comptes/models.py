import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.text import slugify

from apps.core.models import HorodatageModel


class Organisation(HorodatageModel):
    class Secteur(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVE = "prive", "Privé"

    nom = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    secteur = models.CharField(max_length=10, choices=Secteur.choices)
    siret = models.CharField(max_length=14, blank=True)
    ia_activee = models.BooleanField("IA activée", default=True)
    prefixe_stockage = models.CharField(max_length=100, unique=True, editable=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)[:80]
        if not self.prefixe_stockage:
            self.prefixe_stockage = f"org/{self.id}"
        super().save(*args, **kwargs)


class Role(HorodatageModel):
    """Rôle d'organisation (admin, membre, auditeur en lecture seule) ou rôle d'acteur projet
    (autorité d'homologation, RSSI, chef de projet...). `organisation` vide = rôle système."""

    class Portee(models.TextChoices):
        ORGANISATION = "organisation", "Organisation"
        PROJET = "projet", "Projet"

    organisation = models.ForeignKey(Organisation, null=True, blank=True, on_delete=models.CASCADE, related_name="roles")
    code = models.SlugField(max_length=50)
    libelle = models.CharField(max_length=100)
    portee = models.CharField(max_length=12, choices=Portee.choices)
    lecture_seule = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["portee", "libelle"]
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "portee", "code"], name="role_unique", nulls_distinct=False
            ),
        ]

    def __str__(self):
        return self.libelle


class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("L'email est obligatoire.")
        utilisateur = self.model(email=self.normalize_email(email), **extra)
        utilisateur.set_password(password)
        utilisateur.save(using=self._db)
        return utilisateur

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self._create_user(email, password, **extra)


class Utilisateur(AbstractUser):
    """Un utilisateur appartient à une seule organisation. Seul le staff plateforme peut ne pas en avoir."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField("email", unique=True)
    organisation = models.ForeignKey(
        Organisation, null=True, blank=True, on_delete=models.PROTECT, related_name="utilisateurs"
    )
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="utilisateurs",
        limit_choices_to={"portee": Role.Portee.ORGANISATION},
    )
    fonction = models.CharField(max_length=150, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UtilisateurManager()

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.CheckConstraint(
                name="utilisateur_organisation_ou_staff",
                condition=models.Q(organisation__isnull=False) | models.Q(is_staff=True),
            ),
        ]

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def est_lecture_seule(self):
        return bool(self.role and self.role.lecture_seule)
