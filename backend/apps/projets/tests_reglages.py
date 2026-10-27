"""Réglages du projet : droits (administrateurs du projet), statuts réservés, référentiels, acteurs (un chef de
projet au minimum), décision d'homologation par la seule autorité d'homologation, archivage en lecture seule,
revue périodique et rappels, export calendrier."""

from datetime import date, timedelta

from rest_framework.test import APIClient

from apps.audit.models import JournalAudit
from apps.comptes.models import Role
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role
from apps.projets.models import ActeurProjet, Projet
from apps.suivi.models import Notification, Tache
from apps.suivi.services import plan_du_projet

from .reglages import ajouter_mois, rappeler_revues

DANS_3_ANS = (date.today() + timedelta(days=3 * 365)).isoformat()


class ReglagesTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet = self.creer_projet(self.api_a, "Projet A")  # user_a : chef de projet
        self.url = f"/api/projets/{self.projet.id}/"
        self.membre = self.acteur("membre@a.test", "developpeur")
        self.autorite = self.acteur("ah@a.test", "autorite-homologation")
        self.rssi = self.acteur("rssi@a.test", "rssi")

    def acteur(self, email, code):
        u = f.utilisateur(self.org_a, email)
        ActeurProjet.objects.create(projet=self.projet, utilisateur=u, role=f.role_projet(code) if code == "developpeur" else role(Role.Portee.PROJET, code))
        client = APIClient()
        client.force_login(u)
        return client

    def test_reglages_reserves_aux_administrateurs_du_projet(self):
        self.assertEqual(self.membre.patch(self.url, {"nom": "x"}, format="json").status_code, 403)
        self.assertEqual(self.api_a.patch(self.url, {"nom": "Projet A renommé", "periodicite_revue_mois": 6}, format="json").status_code, 200)
        self.assertEqual(self.rssi.patch(self.url, {"notifications_actives": False}, format="json").status_code, 200)
        self.assertEqual(self.api_b.patch(self.url, {"nom": "x"}, format="json").status_code, 404)
        self.assertEqual(self.api_a.patch(self.url, {"periodicite_revue_mois": 0}, format="json").status_code, 400)

    def test_statuts_de_decision_non_modifiables(self):
        for statut in ("homologue", "refuse", "archive"):
            self.assertEqual(self.api_a.patch(self.url, {"statut": statut}, format="json").status_code, 400)
        self.assertEqual(self.api_a.patch(self.url, {"statut": "en_attente_decision"}, format="json").status_code, 200)

    def test_referentiels_un_a_trois(self):
        self.assertEqual(self.api_a.patch(self.url, {"referentiels": []}, format="json").status_code, 400)
        r = self.api_a.patch(self.url, {"referentiels": [str(self.rgs.id), str(self.hygiene.id)]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.projet.referentiels.count(), 2)
        self.assertEqual(self.membre.post("/api/projet-referentiels/", {"projet": str(self.projet.id), "referentiel": str(self.prive_a.id)},
                                          format="json").status_code, 403)

    def test_acteurs_et_dernier_chef_de_projet(self):
        r = self.membre.post("/api/acteurs/", {"projet": str(self.projet.id), "email": "x@ext.test", "nom": "Externe",
                                               "role": str(role(Role.Portee.PROJET, "rssi").id)}, format="json")
        self.assertEqual(r.status_code, 403, r.content)
        r = self.api_a.post("/api/acteurs/", {"projet": str(self.projet.id), "email": "x@ext.test", "nom": "Externe",
                                              "role": str(role(Role.Portee.PROJET, "rssi").id)}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        chef = ActeurProjet.objects.get(projet=self.projet, role__code="chef-projet")
        self.assertEqual(self.api_a.delete(f"/api/acteurs/{chef.id}/").status_code, 400)
        r = self.api_a.patch(f"/api/acteurs/{chef.id}/", {"role": str(role(Role.Portee.PROJET, "rssi").id)}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_decision_par_la_seule_autorite_d_homologation(self):
        url = f"{self.url}decision/"
        donnees = {"decision": "homologation", "date_fin_validite": DANS_3_ANS, "commentaire": "Risques résiduels acceptés."}
        for client in (self.api_a, self.rssi, self.membre, self.client_admin()):
            self.assertEqual(client.post(url, donnees, format="json").status_code, 403)
        self.assertEqual(self.autorite.post(url, {"decision": "homologation"}, format="json").status_code, 400)  # sans fin de validité
        self.assertEqual(self.autorite.post(url, {"decision": "refus"}, format="json").status_code, 400)  # refus non motivé
        r = self.autorite.post(url, donnees, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.projet.refresh_from_db()
        self.assertEqual((self.projet.statut, self.projet.decision, self.projet.date_decision), ("homologue", "homologation", date.today()))
        self.assertEqual(self.projet.date_prochaine_revue, ajouter_mois(date.today(), 12))
        self.assertTrue(JournalAudit.objects.filter(action="decision", objet_id=str(self.projet.id)).exists())
        self.assertTrue(Notification.objects.filter(destinataire=self.user_a, type_evenement="homologation.decision").exists())

    def client_admin(self):
        client = APIClient()
        client.force_login(self.admin_a)
        return client

    def test_archive_en_lecture_seule_puis_desarchive(self):
        self.assertEqual(self.membre.post(f"{self.url}archiver/").status_code, 403)
        self.assertEqual(self.api_a.post(f"{self.url}archiver/").status_code, 200)
        self.assertEqual(self.api_a.patch(self.url, {"nom": "x"}, format="json").status_code, 403)
        r = self.api_a.post("/api/documents-attendus/", {"projet": str(self.projet.id), "intitule": "x"}, format="json")
        self.assertIn(r.status_code, (400, 403))
        self.assertEqual(self.api_a.get(f"{self.url}tableau-de-bord/").data["projet"]["lecture_seule"], True)
        self.assertEqual(self.api_a.post(f"{self.url}desarchiver/").status_code, 200)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.statut, "brouillon")  # statut d'avant l'archivage

    def test_revue_faite_et_rappels(self):
        self.projet.date_prochaine_revue = date.today() + timedelta(days=10)
        self.projet.save()
        self.assertEqual(rappeler_revues(), 1)
        self.assertEqual(rappeler_revues(), 0)  # une seule fois par échéance
        self.assertTrue(Notification.objects.filter(destinataire=self.user_a, type_evenement="revue.rappel").exists())
        Projet.objects.filter(pk=self.projet.pk).update(date_prochaine_revue=date.today() - timedelta(days=1))
        self.assertEqual(rappeler_revues(), 1)  # puis le rappel de retard
        elements = self.api_a.get(f"{self.url}tableau-de-bord/").data["pour_vous"]
        self.assertIn("Revue périodique en retard", [e["titre"] for e in elements])
        r = self.api_a.post(f"{self.url}revue-faite/")
        self.assertEqual(r.data["date_prochaine_revue"], ajouter_mois(date.today(), 12).isoformat())
        self.assertEqual(self.membre.post(f"{self.url}revue-faite/").status_code, 403)

    def test_calendrier(self):
        Tache.objects.create(projet=self.projet, plan=plan_du_projet(self.projet), titre="Corriger, vite ; « urgent »",
                             echeance=date.today() + timedelta(days=5))
        r = self.api_a.get(f"{self.url}calendrier/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/calendar; charset=utf-8")
        texte = r.content.decode()
        self.assertTrue(texte.startswith("BEGIN:VCALENDAR"))
        self.assertIn("Corriger\\, vite \\; « urgent »", texte.replace("\r\n ", ""))
        self.assertTrue(all(len(l.encode()) <= 75 for l in texte.split("\r\n")))
        self.assertEqual(self.api_b.get(f"{self.url}calendrier/").status_code, 404)
        self.api_a.patch(self.url, {"calendrier_actif": False}, format="json")
        self.assertEqual(self.api_a.get(f"{self.url}calendrier/").status_code, 404)

    def test_ajouter_mois(self):
        self.assertEqual(ajouter_mois(date(2027, 1, 31), 1), date(2027, 2, 28))
        self.assertEqual(ajouter_mois(date(2027, 11, 15), 3), date(2028, 2, 15))
