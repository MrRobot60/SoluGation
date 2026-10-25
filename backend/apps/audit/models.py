"""Journal d'audit append-only, chaîné par hash (toute altération casse la chaîne).
Protection applicative ici ; protection base (trigger + REVOKE UPDATE/DELETE) ajoutée à la migration."""

import hashlib
import json

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils import timezone


class JournalImmuable(Exception):
    pass


class JournalAuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise JournalImmuable("Le journal d'audit est en ajout seul.")

    def delete(self):
        raise JournalImmuable("Le journal d'audit est en ajout seul.")

    def pour_organisation(self, organisation):
        return self.filter(organisation=organisation)


class JournalAudit(models.Model):
    class Action(models.TextChoices):
        CREATION = "creation", "Création"
        MODIFICATION = "modification", "Modification"
        SUPPRESSION = "suppression", "Suppression"
        CONSULTATION = "consultation", "Consultation sensible"
        TELECHARGEMENT = "telechargement", "Téléchargement"
        VALIDATION_IA = "validation_ia", "Validation d'une conclusion IA"
        DECISION = "decision", "Décision (homologation, dérogation)"
        CONNEXION = "connexion", "Connexion"
        EXPORT = "export", "Export / rapport"

    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("comptes.Organisation", on_delete=models.PROTECT, related_name="+")
    horodatage = models.DateTimeField(default=timezone.now, db_index=True)
    acteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    acteur_repr = models.CharField(max_length=255, help_text="Figé au moment de l'action.")
    action = models.CharField(max_length=16, choices=Action.choices)
    projet = models.ForeignKey("projets.Projet", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    objet_type = models.CharField(max_length=100)
    objet_id = models.CharField(max_length=64)
    objet_repr = models.CharField(max_length=300, blank=True)
    donnees = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder, help_text="Diff avant/après.")
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    hash_precedent = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, unique=True)

    objects = JournalAuditQuerySet.as_manager()

    class Meta:
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"
        ordering = ["organisation", "id"]
        indexes = [models.Index(fields=["organisation", "projet", "horodatage"])]

    def calculer_hash(self):
        contenu = json.dumps(
            {
                "precedent": self.hash_precedent,
                "organisation": str(self.organisation_id),
                "horodatage": self.horodatage.isoformat(),
                "acteur": str(self.acteur_id),
                "action": self.action,
                "projet": str(self.projet_id),
                "objet": [self.objet_type, self.objet_id],
                "donnees": self.donnees,
            },
            sort_keys=True,
            cls=DjangoJSONEncoder,
        )
        return hashlib.sha256(contenu.encode()).hexdigest()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise JournalImmuable("Le journal d'audit est en ajout seul.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise JournalImmuable("Le journal d'audit est en ajout seul.")

    @classmethod
    def enregistrer(cls, organisation, action, objet, acteur=None, projet=None, donnees=None, ip=None, user_agent=""):
        """Seul point d'entrée d'écriture. Verrouille l'organisation pour sérialiser la chaîne."""
        from apps.comptes.models import Organisation

        with transaction.atomic():
            Organisation.objects.select_for_update().filter(pk=organisation.pk).first()
            dernier = cls.objects.filter(organisation=organisation).order_by("-id").values_list("hash", flat=True).first()
            entree = cls(
                organisation=organisation,
                acteur=acteur,
                acteur_repr=str(acteur) if acteur else "système",
                action=action,
                projet=projet,
                objet_type=objet._meta.label,
                objet_id=str(objet.pk),
                objet_repr=str(objet)[:300],
                donnees=donnees or {},
                adresse_ip=ip,
                user_agent=user_agent[:255],
                hash_precedent=dernier or "0" * 64,
            )
            entree.hash = entree.calculer_hash()
            entree.save()
            return entree
