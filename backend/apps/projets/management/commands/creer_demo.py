"""Jeu de données de démonstration (dev uniquement), rejouable sans doublon.
Compte admin lu dans DEV_ADMIN_EMAIL / DEV_ADMIN_PASSWORD (.env local)."""

import os
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import JournalAudit
from apps.comptes.models import Organisation, Role, Utilisateur
from apps.projets.models import ActeurProjet, DocumentAttendu, Projet, ProjetReferentiel, StatutMesure
from apps.referentiels.models import Mesure, Referentiel
from apps.suivi.models import ActionPlan, Tache

ROLES_PROJET = [
    ("autorite-homologation", "Autorité d'homologation", False),
    ("rssi", "RSSI", False),
    ("chef-projet", "Chef de projet", False),
    ("auditeur", "Auditeur (lecture seule)", True),
]
ROLES_ORGANISATION = [("admin", "Administrateur", False), ("membre", "Membre", False), ("auditeur", "Auditeur", True)]


class Command(BaseCommand):
    help = "Crée une organisation, un projet et un compte admin de démonstration (développement uniquement)."

    @transaction.atomic
    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError("Réservé au développement (DJANGO_DEBUG=True).")
        email, mdp = os.environ.get("DEV_ADMIN_EMAIL"), os.environ.get("DEV_ADMIN_PASSWORD")
        if not (email and mdp):
            raise CommandError("DEV_ADMIN_EMAIL et DEV_ADMIN_PASSWORD absents du .env.")
        referentiels = {r.code: r for r in Referentiel.objects.filter(organisation=None, code__in=["rgs", "hygiene-anssi", "owasp-asvs"])}
        if len(referentiels) < 3:
            raise CommandError("Importer d'abord les référentiels : manage.py importer_referentiel libres")

        for code, libelle, ro in ROLES_ORGANISATION:
            Role.objects.get_or_create(organisation=None, portee=Role.Portee.ORGANISATION, code=code, defaults={"libelle": libelle, "lecture_seule": ro})
        roles = {}
        for code, libelle, ro in ROLES_PROJET:
            roles[code], _ = Role.objects.get_or_create(organisation=None, portee=Role.Portee.PROJET, code=code, defaults={"libelle": libelle, "lecture_seule": ro})

        org, _ = Organisation.objects.get_or_create(slug="demo", defaults={"nom": "Démo SoluGation", "secteur": Organisation.Secteur.PUBLIC})
        admin = Utilisateur.objects.filter(email=email).first()
        if admin is None:
            admin = Utilisateur.objects.create_superuser(email=email, password=mdp, first_name="Admin", last_name="Démo", organisation=org)
        admin.role = Role.objects.get(organisation=None, portee=Role.Portee.ORGANISATION, code="admin")
        admin.save()
        rssi, _ = Utilisateur.objects.get_or_create(
            email="rssi@demo.solugation.test",
            defaults={"first_name": "Camille", "last_name": "Martin", "organisation": org, "fonction": "RSSI", "is_active": False},
        )

        projet, cree = Projet.objects.get_or_create(
            organisation=org, nom="Portail usagers",
            defaults={
                "description": "Application web de démarches en ligne.", "type_bien": Projet.TypeBien.APPLICATION,
                "niveau_vise": Projet.NiveauVise.STANDARD, "statut": Projet.Statut.EN_COURS, "ebios_active": True,
                "cree_par": admin, "date_prochaine_revue": date.today() + timedelta(days=365),
            },
        )
        if not cree:
            self.stdout.write("Démo déjà présente : rien à faire.")
            return
        for ref in referentiels.values():
            ProjetReferentiel.objects.create(projet=projet, referentiel=ref)
        chef = ActeurProjet.objects.create(projet=projet, utilisateur=admin, role=roles["chef-projet"])
        acteur_rssi = ActeurProjet.objects.create(projet=projet, utilisateur=rssi, role=roles["rssi"])
        ActeurProjet.objects.create(projet=projet, nom="Direction générale", email="dg@demo.solugation.test", role=roles["autorite-homologation"])

        rgs = referentiels["rgs"]
        for intitule, ident, jours, resp in [
            ("Analyse de risques", "§2.1", 15, acteur_rssi),
            ("Dossier d'architecture technique", "§2.3", 30, chef),
            ("Rapport d'audit de sécurité", "§7.11", 45, acteur_rssi),
        ]:
            doc = DocumentAttendu.objects.create(projet=projet, intitule=intitule, responsable=resp, echeance=date.today() + timedelta(days=jours))
            doc.mesures.add(Mesure.objects.get(referentiel=rgs, identifiant=ident))

        statuts = [StatutMesure.Statut.CONFORME, StatutMesure.Statut.PARTIEL, StatutMesure.Statut.MANQUANT, StatutMesure.Statut.NON_APPLICABLE]
        for i, mesure in enumerate(referentiels["hygiene-anssi"].mesures.order_by("ordre")[:12]):
            StatutMesure.objects.create(projet=projet, mesure=mesure, statut=statuts[i % 4], evalue_par=admin)

        plan = ActionPlan.objects.create(projet=projet)
        for mesure in referentiels["hygiene-anssi"].mesures.order_by("ordre")[2:12:4]:
            Tache.objects.create(
                projet=projet, plan=plan, mesure=mesure, titre=f"Mettre en œuvre : {mesure.intitule}"[:300],
                responsable=acteur_rssi, echeance=date.today() + timedelta(days=30),
                preuve_attendue="Procédure validée et preuve de mise en œuvre.", priorite=Tache.Priorite.HAUTE,
            )
        JournalAudit.enregistrer(org, JournalAudit.Action.CREATION, projet, acteur=admin, projet=projet, donnees={"source": "creer_demo"})
        self.stdout.write(self.style.SUCCESS(f"Démo créée : organisation « {org} », projet « {projet} », compte {email}."))
