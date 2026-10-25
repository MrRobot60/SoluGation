"""Jeu de données de démonstration (dev uniquement), rejouable sans doublon.
Compte admin lu dans DEV_ADMIN_EMAIL / DEV_ADMIN_PASSWORD (.env local)."""

import os
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.ai.models import AnalyseIA, ResultatAnalyseMesure
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
            self._enrichir(projet, admin, referentiels)
            self.stdout.write("Démo déjà présente : compléments vérifiés.")
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
        self._enrichir(projet, admin, referentiels)
        self.stdout.write(self.style.SUCCESS(f"Démo créée : organisation « {org} », projet « {projet} », compte {email}."))

    def _enrichir(self, projet, admin, referentiels):
        """Évaluations sur tous les référentiels, analyse IA à valider, tâches de l'admin (dont une en retard)."""
        cycle = [StatutMesure.Statut.CONFORME] * 4 + [StatutMesure.Statut.PARTIEL] * 2 + [
            StatutMesure.Statut.MANQUANT, StatutMesure.Statut.NON_APPLICABLE]
        for ref, part in ((referentiels["rgs"], 0.75), (referentiels["owasp-asvs"], 0.7), (referentiels["hygiene-anssi"], 0.85)):
            mesures = list(ref.mesures.order_by("ordre"))
            for i, mesure in enumerate(mesures[: int(len(mesures) * part)]):
                StatutMesure.objects.get_or_create(projet=projet, mesure=mesure,
                                                   defaults={"statut": cycle[i % len(cycle)], "evalue_par": admin})

        if not AnalyseIA.objects.filter(projet=projet).exists():
            analyse = AnalyseIA.objects.create(
                projet=projet, type_analyse=AnalyseIA.Type.ANALYSE_DOCUMENTAIRE, etat=AnalyseIA.Etat.TERMINEE,
                fournisseur="démo", modele="démo", version_prompt="0", demandee_par=admin,
                debut_le=timezone.now() - timedelta(hours=2), fin_le=timezone.now() - timedelta(hours=2),
            )
            for ref, ident, couverture in (("hygiene-anssi", "M04", "couvert"), ("rgs", "§2.3", "partiel"),
                                           ("hygiene-anssi", "M37", "absent")):
                ResultatAnalyseMesure.objects.create(
                    projet=projet, analyse=analyse, mesure=Mesure.objects.get(referentiel=referentiels[ref], identifiant=ident),
                    couverture=couverture, justification="Exemple de démonstration.",
                )

        plan = ActionPlan.objects.get(projet=projet)
        chef = ActeurProjet.objects.get(projet=projet, utilisateur=admin)
        hygiene = referentiels["hygiene-anssi"]
        for ident, jours in (("M12", -5), ("M03", 30)):
            mesure = Mesure.objects.get(referentiel=hygiene, identifiant=ident)
            Tache.objects.get_or_create(
                projet=projet, plan=plan, mesure=mesure, responsable=chef,
                defaults={"titre": mesure.intitule[:300], "echeance": date.today() + timedelta(days=jours),
                          "preuve_attendue": "Procédure et capture de configuration", "priorite": Tache.Priorite.HAUTE},
            )
