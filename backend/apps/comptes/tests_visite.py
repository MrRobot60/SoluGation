"""Visite guidée : projet d'exemple propre à l'utilisateur, jamais visible d'une autre organisation."""

from rest_framework.test import APIClient

from apps.comptes.models import Role
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role
from apps.projets.models import ActeurProjet, Projet, StatutMesure


class VisiteTests(BaseApi):
    def demarrer(self, client):
        r = client.post("/api/auth/moi/visite/", {"action": "demarrer"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.data["projet"]

    def test_projet_exemple_cree_une_fois(self):
        self.assertFalse(self.api_a.get("/api/auth/moi/").data["visite_terminee"])
        id_projet = self.demarrer(self.api_a)
        self.assertEqual(self.demarrer(self.api_a), id_projet)
        projet = Projet.objects.get(pk=id_projet)
        self.assertTrue(projet.exemple)
        self.assertFalse(projet.notifications_actives)  # pas de mail vers le contact fictif
        self.assertTrue(ActeurProjet.objects.filter(projet=projet, utilisateur=self.user_a, role__code="chef-projet").exists())
        self.assertTrue(StatutMesure.objects.filter(projet=projet).exists())
        self.assertTrue(self.api_a.get(f"/api/projets/{id_projet}/").data["exemple"])

    def test_isolation(self):
        id_projet = self.demarrer(self.api_a)
        self.assertEqual(self.api_b.get(f"/api/projets/{id_projet}/").status_code, 404)
        id_b = self.demarrer(self.api_b)
        self.assertNotEqual(id_b, id_projet)
        self.assertEqual(Projet.objects.get(pk=id_b).organisation, self.org_b)
        # Deux utilisateurs de la même organisation : un exemple chacun, noms distincts.
        autre = APIClient()
        autre.force_login(f.utilisateur(self.org_a, "autre@a.test"))
        id_autre = self.demarrer(autre)
        self.assertNotEqual(id_autre, id_projet)
        self.assertEqual(self.api_a.get(f"/api/projets/{id_autre}/").status_code, 404)

    def test_lecture_seule_ne_cree_rien(self):
        auditeur = f.utilisateur(self.org_a, "audit@a.test")
        auditeur.role = role(Role.Portee.ORGANISATION, "auditeur")
        auditeur.save()
        client = APIClient()
        client.force_login(auditeur)
        self.assertIsNone(self.demarrer(client))
        self.assertFalse(Projet.objects.filter(exemple=True).exists())

    def test_terminer_puis_revoir(self):
        for action, attendu in (("terminer", True), ("revoir", False)):
            self.assertEqual(self.api_a.post("/api/auth/moi/visite/", {"action": action}, format="json").status_code, 204)
            self.assertEqual(self.api_a.get("/api/auth/moi/").data["visite_terminee"], attendu)
        self.assertEqual(self.api_a.post("/api/auth/moi/visite/", {"action": "x"}, format="json").status_code, 400)
