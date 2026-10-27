"""Bibliothèque : un référentiel privé (copie ISO licenciée) n'est jamais visible d'une autre organisation, ni
par la liste, ni par la recherche, ni par une correspondance ; le texte n'est servi que s'il est embarqué."""

from rest_framework.test import APIClient

from apps.comptes.models import Role
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role

from .models import CorrespondanceMesure, Licence, Mesure, Referentiel


class BibliothequeTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.iso_a = Mesure.objects.get(referentiel=self.prive_a)
        Mesure.objects.filter(pk=self.iso_a.pk).update(texte_officiel="TEXTE ISO CONFIDENTIEL", categorie="Organisationnelles")
        Referentiel.objects.filter(pk=self.prive_a.pk).update(texte_embarque=True)
        self.nist = Referentiel.objects.create(code="nist-csf", nom="NIST CSF", version="2.0", licence=Licence.LIBRE, texte_embarque=False)
        self.gv = Mesure.objects.create(referentiel=self.nist, identifiant="GV.PO-01", intitule="Politique établie", texte_officiel="Texte NIST",
                                        categorie="Gouverner", ordre=1)
        Mesure.objects.create(referentiel=self.nist, identifiant="ID.AM-01", intitule="Inventaire du matériel", categorie="Identifier", ordre=2)
        Mesure.objects.filter(pk=self.mesure_rgs.pk).update(texte_officiel="Texte libre RGS")
        Referentiel.objects.filter(pk=self.rgs.pk).update(texte_embarque=True)

    def test_referentiel_prive_invisible_ailleurs(self):
        codes_b = {r["code"] for r in self.api_b.get("/api/referentiels/").data}
        self.assertNotIn("iso27001", codes_b)
        self.assertIn("iso27001", {r["code"] for r in self.api_a.get("/api/referentiels/").data})
        self.assertEqual(self.api_b.get(f"/api/mesures/{self.iso_a.id}/").status_code, 404)
        self.assertEqual(self.api_b.get("/api/mesures/?q=CONFIDENTIEL").data["count"], 0)
        self.assertEqual(self.api_a.get("/api/mesures/?q=CONFIDENTIEL").data["count"], 1)  # sa propre copie
        self.assertEqual(self.api_b.get(f"/api/referentiels/{self.prive_a.id}/categories/").status_code, 404)

    def test_texte_servi_seulement_s_il_est_embarque(self):
        self.assertIsNone(self.api_a.get(f"/api/mesures/{self.gv.id}/").data["texte_officiel"])
        self.assertEqual(self.api_a.get("/api/mesures/?q=Texte NIST").data["count"], 0)  # pas de recherche dans un texte non servi
        self.assertEqual(self.api_a.get(f"/api/mesures/{self.mesure_rgs.id}/").data["texte_officiel"], "Texte libre RGS")

    def test_categories_dans_l_ordre(self):
        r = self.api_a.get(f"/api/referentiels/{self.nist.id}/categories/").data
        self.assertEqual([c["categorie"] for c in r], ["Gouverner", "Identifier"])

    def test_correspondances_de_l_organisation(self):
        r = self.api_a.post("/api/correspondances/", {"mesure_source": str(self.iso_a.id), "mesure_cible": str(self.gv.id),
                                                      "type_correspondance": "equivalente", "reference": "Table interne"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        fiche = self.api_a.get(f"/api/mesures/{self.gv.id}/").data
        self.assertEqual([c["mesure"]["identifiant"] for c in fiche["correspondances"]], ["A.5.1"])
        self.assertEqual(fiche["correspondances"][0]["sens"], "entrante")
        # Organisation B : ni la correspondance, ni la mesure ISO de A ne sont visibles.
        self.assertEqual(self.api_b.get(f"/api/mesures/{self.gv.id}/").data["correspondances"], [])
        self.assertEqual(self.api_b.delete(f"/api/correspondances/{r.data['id']}/").status_code, 404)
        r_b = self.api_b.post("/api/correspondances/", {"mesure_source": str(self.iso_a.id), "mesure_cible": str(self.gv.id),
                                                        "type_correspondance": "partielle"}, format="json")
        self.assertEqual(r_b.status_code, 400)
        # Doublon (même dans l'autre sens) et même référentiel refusés.
        inverse = self.api_a.post("/api/correspondances/", {"mesure_source": str(self.gv.id), "mesure_cible": str(self.iso_a.id),
                                                            "type_correspondance": "partielle"}, format="json")
        self.assertEqual(inverse.status_code, 400)
        meme = Mesure.objects.get(identifiant="ID.AM-01")
        self.assertEqual(self.api_a.post("/api/correspondances/", {"mesure_source": str(self.gv.id), "mesure_cible": str(meme.id),
                                                                   "type_correspondance": "partielle"}, format="json").status_code, 400)
        self.assertEqual(self.api_a.delete(f"/api/correspondances/{r.data['id']}/").status_code, 204)
        self.assertFalse(CorrespondanceMesure.objects.exists())

    def test_auditeur_ne_saisit_pas_de_correspondance(self):
        auditeur = f.utilisateur(self.org_a, "audit@a.test")
        auditeur.role = role(Role.Portee.ORGANISATION, "auditeur")
        auditeur.save()
        client = APIClient()
        client.force_login(auditeur)
        r = client.post("/api/correspondances/", {"mesure_source": str(self.iso_a.id), "mesure_cible": str(self.gv.id),
                                                  "type_correspondance": "partielle"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_projets_et_usage_limites_a_l_organisation(self):
        projet_a = self.creer_projet(self.api_a, "Projet A")
        self.creer_projet(self.api_b, "Projet B")
        self.api_a.post("/api/statuts-mesures/", {"projet": str(projet_a.id), "mesure": str(self.mesure_rgs.id), "statut": "conforme"}, format="json")
        rgs_a = next(r for r in self.api_a.get("/api/referentiels/").data if r["code"] == "rgs")
        self.assertEqual(rgs_a["nb_projets"], 1)  # le projet de B n'est pas compté
        fiche_b = self.api_b.get(f"/api/mesures/{self.mesure_rgs.id}/").data
        self.assertEqual(fiche_b["projets"], [])
        self.assertEqual([p["statut"] for p in self.api_a.get(f"/api/mesures/{self.mesure_rgs.id}/").data["projets"]], ["conforme"])
