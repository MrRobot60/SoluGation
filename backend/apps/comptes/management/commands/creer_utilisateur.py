from django.core.management.base import BaseCommand, CommandError

from apps.comptes.models import Organisation, Role, Utilisateur

from ._saisie import mot_de_passe


class Command(BaseCommand):
    help = ("Ajoute un compte à une organisation (rôle admin, membre ou auditeur en lecture seule). "
            "Mot de passe demandé, ou lu dans SOLUGATION_MOT_DE_PASSE.")

    def add_arguments(self, parser):
        parser.add_argument("--organisation", required=True, help="Slug de l'organisation (voir l'admin Django ou creer_organisation).")
        parser.add_argument("--email", required=True)
        parser.add_argument("--role", choices=["admin", "membre", "auditeur"], default="membre")
        parser.add_argument("--prenom", default="")
        parser.add_argument("--nom-famille", default="", dest="nom_famille")
        parser.add_argument("--fonction", default="", help="ex. RSSI, chef de projet, DSI.")

    def handle(self, organisation, email, role, prenom, nom_famille, fonction, **options):
        org = Organisation.objects.filter(slug=organisation).first()
        if org is None:
            raise CommandError(f"Organisation inconnue : {organisation}")
        if Utilisateur.objects.filter(email__iexact=email).exists():
            raise CommandError(f"Un compte existe déjà pour {email}.")
        utilisateur = Utilisateur(email=email.lower(), first_name=prenom, last_name=nom_famille, fonction=fonction, organisation=org,
                                  role=Role.objects.get(organisation=None, portee=Role.Portee.ORGANISATION, code=role))
        utilisateur.set_password(mot_de_passe(utilisateur))
        utilisateur.save()
        self.stdout.write(self.style.SUCCESS(f"Compte {email} ({role}) ajouté à « {org.nom} »."))
