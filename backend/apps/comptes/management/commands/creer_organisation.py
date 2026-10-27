from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.comptes.models import Organisation, Role, Utilisateur

from ._saisie import mot_de_passe


class Command(BaseCommand):
    help = ("Crée une organisation et son premier administrateur. --admin-installation en fait aussi l'administrateur "
            "de l'installation (configuration de l'IA, admin Django). Mot de passe demandé, ou lu dans SOLUGATION_MOT_DE_PASSE.")

    def add_arguments(self, parser):
        parser.add_argument("--nom", required=True, help="Nom de l'organisation.")
        parser.add_argument("--secteur", choices=["public", "prive"], default="public")
        parser.add_argument("--email", required=True, help="Email de l'administrateur (identifiant de connexion).")
        parser.add_argument("--prenom", default="")
        parser.add_argument("--nom-famille", default="", dest="nom_famille")
        parser.add_argument("--admin-installation", action="store_true", help="Administrateur de toute l'installation.")

    @transaction.atomic
    def handle(self, nom, secteur, email, prenom, nom_famille, admin_installation, **options):
        if Utilisateur.objects.filter(email__iexact=email).exists():
            raise CommandError(f"Un compte existe déjà pour {email}.")
        slug = slugify(nom)[:80] or "organisation"
        if Organisation.objects.filter(slug=slug).exists():
            raise CommandError(f"Une organisation « {slug} » existe déjà.")
        org = Organisation.objects.create(nom=nom, slug=slug, secteur=secteur)
        role = Role.objects.get(organisation=None, portee=Role.Portee.ORGANISATION, code="admin")
        utilisateur = Utilisateur(email=email.lower(), first_name=prenom, last_name=nom_famille, organisation=org, role=role,
                                  is_staff=admin_installation, is_superuser=admin_installation)
        utilisateur.set_password(mot_de_passe(utilisateur))
        utilisateur.save()
        portee = "de l'organisation et de l'installation" if admin_installation else "de l'organisation"
        self.stdout.write(self.style.SUCCESS(f"Organisation « {org.nom} » ({org.slug}) créée ; {email} en est l'administrateur {portee}."))
