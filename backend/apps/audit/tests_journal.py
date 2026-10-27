"""Journal d'audit : filtres, isolation (organisation, projet, entrées hors projet réservées à l'administrateur),
export tracé, et vérification d'intégrité qui détecte une modification ou une suppression faite en base."""

from datetime import timedelta

from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi

from .api import verifier_chaine
from .models import JournalAudit

URL = "/api/journal/"


def sans_verrou(sql, params=()):
    """Simule une attaque directe en base : le trigger d'immuabilité est levé le temps de la requête."""
    with connection.cursor() as c:
        c.execute("SET CONSTRAINTS ALL IMMEDIATE")  # contrôles différés en attente : ALTER TABLE les refuserait
        c.execute("ALTER TABLE audit_journalaudit DISABLE TRIGGER journal_audit_pas_de_modification")
        c.execute(sql, params)
        c.execute("ALTER TABLE audit_journalaudit ENABLE TRIGGER journal_audit_pas_de_modification")


class JournalTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet = self.creer_projet(self.api_a, "Projet A")
        self.api_a.post("/api/documents-attendus/", {"projet": str(self.projet.id), "intitule": "PSSI"}, format="json")
        self.api_admin = APIClient()
        self.api_admin.force_login(self.admin_a)
        JournalAudit.enregistrer(organisation=self.org_a, action=JournalAudit.Action.CONNEXION, objet=self.admin_a, acteur=self.admin_a)

    def ids(self, reponse):
        return [e["id"] for e in reponse.data["results"]]

    def test_filtres(self):
        self.assertEqual({e["action"] for e in self.api_a.get(f"{URL}?action=creation").data["results"]}, {"creation"})
        self.assertTrue(all(e["objet_libelle"] == "Document attendu" for e in self.api_a.get(f"{URL}?q=PSSI").data["results"]))
        demain = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertEqual(self.api_a.get(f"{URL}?du={demain}").data["count"], 0)
        self.assertGreater(self.api_a.get(f"{URL}?projet={self.projet.id}").data["count"], 0)
        self.assertEqual([a["nom"] for a in self.api_a.get(f"{URL}acteurs/").data], ["chef@a.test"])

    def test_isolation_et_hors_projet(self):
        self.assertEqual(self.api_b.get(URL).data["count"], 0)
        self.assertEqual(self.api_b.get(f"{URL}?projet={self.projet.id}").data["count"], 0)
        connexion = JournalAudit.objects.get(action="connexion").id
        self.assertNotIn(connexion, self.ids(self.api_a.get(f"{URL}?hors_projet=1")))  # membre : jamais les entrées hors projet
        self.assertIn(connexion, self.ids(self.api_admin.get(f"{URL}?hors_projet=1")))
        autre = f.utilisateur(self.org_a, "autre@a.test")  # membre de l'organisation, mais pas du projet
        client = APIClient()
        client.force_login(autre)
        self.assertEqual(client.get(URL).data["count"], 0)

    def test_export_trace(self):
        r = self.api_a.get(f"{URL}exporter/?action=creation")
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        texte = r.content.decode("utf-8-sig")
        self.assertTrue(texte.startswith("id;horodatage;auteur"))
        self.assertIn("PSSI", texte)
        self.assertTrue(JournalAudit.objects.filter(action="export", donnees__export="journal").exists())
        self.assertNotIn("PSSI", self.api_b.get(f"{URL}exporter/").content.decode("utf-8-sig"))

    def test_integrite(self):
        self.assertEqual(self.api_a.get(f"{URL}integrite/").status_code, 403)
        r = self.api_admin.get(f"{URL}integrite/")
        self.assertTrue(r.data["integre"], r.data)
        self.assertEqual(len(r.data["derniere_empreinte"]), 64)

    def test_modification_en_base_detectee(self):
        cible = JournalAudit.objects.filter(organisation=self.org_a).order_by("id")[1]
        sans_verrou("UPDATE audit_journalaudit SET donnees = %s WHERE id = %s", ['{"falsifie": true}', cible.id])
        resultat = verifier_chaine(self.org_a)
        self.assertEqual((resultat["integre"], resultat["anomalie"]["id"]), (False, cible.id))
        self.assertIn("modifié", resultat["anomalie"]["nature"])

    def test_suppression_en_base_detectee(self):
        entrees = list(JournalAudit.objects.filter(organisation=self.org_a).order_by("id"))
        sans_verrou("DELETE FROM audit_journalaudit WHERE id = %s", [entrees[1].id])
        resultat = verifier_chaine(self.org_a)
        self.assertEqual((resultat["integre"], resultat["anomalie"]["id"]), (False, entrees[2].id))
        self.assertIn("chaînage", resultat["anomalie"]["nature"])
        self.assertTrue(verifier_chaine(self.org_b)["integre"])  # l'autre organisation n'est pas affectée
