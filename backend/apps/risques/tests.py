"""Registre des risques résiduels et dérogations : isolation entre organisations, décisions réservées aux
décisionnaires (datées, nominatives, motivées), acceptation levée quand le risque change, dérogation figée
après décision, expiration automatique, notifications."""

from datetime import date, timedelta

from rest_framework.test import APIClient

from apps.audit.models import JournalAudit
from apps.comptes.models import Role
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role
from apps.projets.models import ActeurProjet
from apps.suivi.models import Notification

from .api import expirer_derogations
from .models import Derogation, RisqueResiduel

DEMAIN = (date.today() + timedelta(days=1)).isoformat()
DANS_UN_AN = (date.today() + timedelta(days=365)).isoformat()


class RegistreTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet = self.creer_projet(self.api_a, "Projet A")
        self.rssi = f.utilisateur(self.org_a, "rssi@a.test")
        ActeurProjet.objects.create(projet=self.projet, utilisateur=self.rssi, role=role(Role.Portee.PROJET, "rssi"))
        self.api_rssi = self.client_pour(self.rssi)

    def client_pour(self, utilisateur):
        client = APIClient()
        client.force_login(utilisateur)
        return client

    def risque(self, **extra):
        r = self.api_a.post("/api/risques-residuels/", {"projet": str(self.projet.id), "intitule": "Fuite de données", "gravite": 3,
                                                        "vraisemblance": 2, **extra}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.data["id"]

    def derogation(self, **extra):
        r = self.api_a.post("/api/derogations/", {"projet": str(self.projet.id), "mesure": str(self.mesure_rgs.id),
                                                  "motif": "Application héritée, remplacement prévu.", "date_expiration": DANS_UN_AN, **extra},
                            format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.data["id"]

    def test_isolation_entre_organisations(self):
        rid, did = self.risque(), self.derogation()
        for url in (f"/api/risques-residuels/{rid}/", f"/api/derogations/{did}/"):
            self.assertEqual(self.api_b.get(url).status_code, 404)
            self.assertEqual(self.api_b.patch(url, {"motif": "x", "intitule": "x"}, format="json").status_code, 404)
            self.assertEqual(self.api_b.post(f"{url}decider/", {"decision": "accepter"}, format="json").status_code, 404)
        self.assertEqual(self.api_b.get("/api/risques-residuels/").data["count"], 0)
        r = self.api_b.post("/api/risques-residuels/", {"projet": str(self.projet.id), "intitule": "x", "gravite": 1, "vraisemblance": 1},
                            format="json")
        self.assertEqual(r.status_code, 400)

    def test_acceptation_reservee_datee_et_motivee(self):
        rid = self.risque()
        url = f"/api/risques-residuels/{rid}/decider/"
        self.assertEqual(self.api_a.post(url, {"decision": "accepter", "motif": "ok", "date_revue": DANS_UN_AN}, format="json").status_code, 403)
        self.assertEqual(self.api_a.patch(f"/api/risques-residuels/{rid}/", {"statut": "accepte"}, format="json").status_code, 400)
        self.assertEqual(self.api_rssi.post(url, {"decision": "accepter", "date_revue": DANS_UN_AN}, format="json").status_code, 400)
        self.assertEqual(self.api_rssi.post(url, {"decision": "accepter", "motif": "ok", "date_revue": date.today().isoformat()},
                                            format="json").status_code, 400)
        r = self.api_rssi.post(url, {"decision": "accepter", "motif": "Risque faible, surveillé", "date_revue": DANS_UN_AN}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        risque = RisqueResiduel.objects.get(pk=rid)
        self.assertEqual((risque.statut, risque.accepte_par, risque.motif_acceptation), ("accepte", self.rssi, "Risque faible, surveillé"))
        self.assertTrue(JournalAudit.objects.filter(action="decision", objet_id=rid).exists())
        self.assertTrue(Notification.objects.filter(destinataire=self.user_a, type_evenement="risque.decision").exists())

    def test_modifier_un_risque_accepte_leve_l_acceptation(self):
        rid = self.risque()
        self.api_rssi.post(f"/api/risques-residuels/{rid}/decider/", {"decision": "accepter", "motif": "ok", "date_revue": DANS_UN_AN}, format="json")
        self.api_a.patch(f"/api/risques-residuels/{rid}/", {"date_revue": DEMAIN}, format="json")  # sans effet sur la cotation
        self.assertEqual(RisqueResiduel.objects.get(pk=rid).statut, "accepte")
        self.api_a.patch(f"/api/risques-residuels/{rid}/", {"gravite": 4}, format="json")
        risque = RisqueResiduel.objects.get(pk=rid)
        self.assertEqual((risque.statut, risque.accepte_par, risque.accepte_le), ("identifie", None, None))
        self.assertTrue(JournalAudit.objects.filter(action="decision", objet_id=rid, donnees__decision="acceptation levée").exists())

    def test_risque_decide_non_supprimable(self):
        rid = self.risque()
        self.api_rssi.post(f"/api/risques-residuels/{rid}/decider/", {"decision": "clore"}, format="json")
        self.assertEqual(self.api_a.delete(f"/api/risques-residuels/{rid}/").status_code, 403)
        libre = self.risque(intitule="Brouillon")
        self.assertEqual(self.api_a.delete(f"/api/risques-residuels/{libre}/").status_code, 204)

    def test_derogation_demande_decision_puis_figee(self):
        did = self.derogation()
        notif = Notification.objects.get(destinataire=self.rssi, type_evenement="derogation.demandee")
        self.assertIn("derogations", notif.lien)
        url = f"/api/derogations/{did}/decider/"
        self.assertEqual(self.api_a.post(url, {"decision": "accepter"}, format="json").status_code, 403)
        self.assertEqual(self.api_rssi.post(url, {"decision": "refuser"}, format="json").status_code, 400)  # refus non motivé
        r = self.api_rssi.post(url, {"decision": "accepter", "commentaire": "Jusqu'à la migration"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        d = Derogation.objects.get(pk=did)
        self.assertEqual((d.statut, d.decidee_par, d.date_decision), ("acceptee", self.rssi, date.today()))
        self.assertEqual(self.api_a.patch(f"/api/derogations/{did}/", {"motif": "Autre"}, format="json").status_code, 400)
        self.assertEqual(self.api_a.delete(f"/api/derogations/{did}/").status_code, 403)
        self.assertEqual(self.api_rssi.post(url, {"decision": "accepter"}, format="json").status_code, 409)
        self.assertTrue(Notification.objects.filter(destinataire=self.user_a, type_evenement="derogation.decision").exists())
        self.api_rssi.post(url, {"decision": "revoquer", "commentaire": "Migration faite"}, format="json")
        self.assertEqual(Derogation.objects.get(pk=did).statut, "expiree")

    def test_acceptation_exige_une_expiration_future(self):
        did = self.derogation(date_expiration=None)
        r = self.api_rssi.post(f"/api/derogations/{did}/decider/", {"decision": "accepter"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api_rssi.post(f"/api/derogations/{did}/decider/", {"decision": "accepter", "date_expiration": DEMAIN}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_expiration_automatique(self):
        did = self.derogation()
        self.api_rssi.post(f"/api/derogations/{did}/decider/", {"decision": "accepter"}, format="json")
        Derogation.objects.filter(pk=did).update(date_expiration=date.today() - timedelta(days=1))
        self.assertEqual(self.api_a.get(f"/api/derogations/{did}/").data["statut"], "expiree")
        self.assertEqual(expirer_derogations(), [])  # déjà traitée, rien à refaire
        self.assertTrue(JournalAudit.objects.filter(objet_id=did, donnees__statut="expiree").exists())

    def test_mesure_hors_projet_refusee(self):
        hors = self.hygiene.mesures.first()
        r = self.api_a.post("/api/derogations/", {"projet": str(self.projet.id), "mesure": str(hors.id), "motif": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api_a.post("/api/derogations/", {"projet": str(self.projet.id), "motif": "Sans objet"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_tableau_de_bord_a_decider(self):
        self.derogation()
        self.risque()
        elements = self.api_rssi.get(f"/api/projets/{self.projet.id}/tableau-de-bord/").data["pour_vous"]
        titres = [e["titre"] for e in elements if e["type"] == "decision"]
        self.assertIn("1 dérogation(s) à décider", titres)
        self.assertIn("1 risque(s) résiduel(s) à statuer", titres)
        self.assertFalse([e for e in self.api_a.get(f"/api/projets/{self.projet.id}/tableau-de-bord/").data["pour_vous"] if e["type"] == "decision"])

    def test_auditeur_en_lecture_seule(self):
        lecteur = f.utilisateur(self.org_a, "lecteur@a.test")
        ActeurProjet.objects.create(projet=self.projet, utilisateur=lecteur, role=role(Role.Portee.PROJET, "auditeur"))
        client = self.client_pour(lecteur)
        rid = self.risque()
        self.assertEqual(client.get(f"/api/risques-residuels/{rid}/").status_code, 200)
        self.assertEqual(client.post("/api/risques-residuels/", {"projet": str(self.projet.id), "intitule": "x", "gravite": 1,
                                                                  "vraisemblance": 1}, format="json").status_code, 403)
        self.assertEqual(client.post(f"/api/risques-residuels/{rid}/decider/", {"decision": "clore"}, format="json").status_code, 403)
