"""Rôles système, communs à toutes les organisations."""

from django.db import migrations

ROLES = [
    # (portée, code, libellé, lecture seule)
    ("organisation", "admin", "Administrateur", False),
    ("organisation", "membre", "Membre", False),
    ("organisation", "auditeur", "Auditeur (lecture seule)", True),
    ("projet", "autorite-homologation", "Autorité d'homologation", False),
    ("projet", "rssi", "RSSI", False),
    ("projet", "chef-projet", "Chef de projet", False),
    ("projet", "contributeur", "Contributeur", False),
    ("projet", "auditeur", "Auditeur (lecture seule)", True),
]


def creer(apps, schema_editor):
    Role = apps.get_model("comptes", "Role")
    for portee, code, libelle, lecture_seule in ROLES:
        Role.objects.update_or_create(
            organisation=None, portee=portee, code=code, defaults={"libelle": libelle, "lecture_seule": lecture_seule}
        )


def supprimer(apps, schema_editor):
    Role = apps.get_model("comptes", "Role")
    for portee, code, *_ in ROLES:
        Role.objects.filter(organisation=None, portee=portee, code=code, utilisateurs=None, acteurs=None).delete()


class Migration(migrations.Migration):
    dependencies = [("comptes", "0001_initial"), ("projets", "0001_initial")]

    operations = [migrations.RunPython(creer, supprimer)]
