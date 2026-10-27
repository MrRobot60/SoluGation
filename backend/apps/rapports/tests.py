"""Rapports : isolation entre organisations, rédaction IA à partir de données minimisées (aucun nom), texte
automatique quand l'IA est coupée ou indisponible, PDF produit sans appel IA, validation réservée aux
décisionnaires et PDF figé empreinté, comparaison avec la version précédente."""

import hashlib
import json
from unittest import mock

from django.test import override_settings

from apps.ai.models import AnalyseIA
from apps.ai.provider import Factice, ReponseIA
from apps.audit.models import JournalAudit
from apps.core.tests.test_api import BaseApi
from apps.projets.models import StatutMesure

from .models import Rapport
from .pdf import chaine_css
from .redaction import chiffres_non_verifies


class Scripte:
    nom, modele = "scripte", "v0"

    def __init__(self, contenu):
        self.contenu, self.messages = contenu, []

    def verifier_configuration(self):
        pass

    def completer_json(self, systeme, utilisateur):
        self.messages.append(utilisateur)
        return ReponseIA(self.contenu, 10, 10)


@override_settings(IA_SYNCHRONE=True)
class RapportTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.user_a.first_name, self.user_a.last_name = "Camille", "Durand"
        self.user_a.save()
        self.projet = self.creer_projet(self.api_a, "Portail")
        StatutMesure.objects.create(projet=self.projet, mesure=self.mesure_rgs, statut="manquant", justification="Aucune analyse.")
        self.api_admin = self.client_pour(self.admin_a)

    def client_pour(self, utilisateur):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_login(utilisateur)
        return client

    def generer(self, client, fournisseur):
        with mock.patch("apps.ai.analyse.obtenir_fournisseur", return_value=fournisseur), \
             self.captureOnCommitCallbacks(execute=True):
            return client.post("/api/rapports/", {"projet": str(self.projet.id)}, format="json")

    def test_redaction_ia_minimisee_et_controlee(self):
        fournisseur = Scripte({"sections": [
            {"cle": "synthese", "texte": "1 manquement constaté ; taux de conformité de 87 %."},  # 87 : inventé
            {"cle": "inconnue", "texte": "Ignorée."},
        ]})
        reponse = self.generer(self.api_a, fournisseur)
        self.assertEqual(reponse.status_code, 201, reponse.content)
        rapport = Rapport.objects.get(pk=reponse.data["id"])
        self.assertEqual(rapport.analyse_ia.etat, AnalyseIA.Etat.TERMINEE, rapport.analyse_ia.erreur)
        sections = {s["cle"]: s for s in rapport.sections}
        self.assertEqual([s["cle"] for s in rapport.sections], ["synthese", "conformite", "documents", "plan_action", "suite"])
        self.assertEqual(sections["synthese"]["source"], "ia")
        self.assertEqual(sections["synthese"]["alertes"], ["87"])
        self.assertEqual(sections["conformite"]["source"], "automatique")  # absente de la réponse
        self.assertEqual(rapport.statut_validation, "a_valider")
        envoye = fournisseur.messages[0]
        for nom in ("Camille", "Durand", "chef@a.test", "Org A", "Portail"):
            self.assertNotIn(nom, envoye)  # aucune personne ni organisation, pas même le nom du projet
        self.assertIn("Aucune analyse.", rapport.donnees["manquements"][0]["justification"])
        self.assertNotIn("Aucune analyse.", envoye)  # constats détaillés non transmis
        self.assertNotIn("EBIOS", envoye)  # méthode non activée : non mentionnée
        # Un taux précalculé fourni à l'IA n'est pas signalé comme inventé.
        taux = json.loads(envoye.split("\n", 1)[1])["synthese_chiffree"]["taux_conformite_global_pct"]
        self.assertEqual(chiffres_non_verifies(f"Conformité globale : {taux} %.", rapport.donnees), [])

    def test_ia_desactivee_texte_automatique(self):
        self.org_a.ia_activee = False
        self.org_a.save()
        fournisseur = Scripte({"sections": []})
        reponse = self.generer(self.api_a, fournisseur)
        self.assertEqual(reponse.status_code, 201)
        rapport = Rapport.objects.get(pk=reponse.data["id"])
        self.assertIsNone(rapport.analyse_ia)
        self.assertEqual({s["source"] for s in rapport.sections}, {"automatique"})
        self.assertEqual(fournisseur.messages, [])

    @override_settings(IA_FOURNISSEUR="scaleway", IA_CLE="", IA_ZDR_CONFIRME=False)
    def test_ia_mal_configuree_rapport_quand_meme(self):
        with mock.patch("apps.ai.provider.OUVREUR.open") as envoi, self.captureOnCommitCallbacks(execute=True):
            reponse = self.api_a.post("/api/rapports/", {"projet": str(self.projet.id)}, format="json")
        self.assertEqual(reponse.status_code, 201)
        self.assertIn("responsabilité", reponse.data["avertissement"])
        self.assertIsNone(Rapport.objects.get(pk=reponse.data["id"]).analyse_ia)
        envoi.assert_not_called()

    def test_pdf_brouillon_sans_appel_ia(self):
        rapport_id = self.generer(self.api_a, Factice()).data["id"]
        with mock.patch("apps.ai.provider.obtenir_fournisseur", side_effect=AssertionError("appel IA interdit")), \
             mock.patch("apps.ai.analyse.obtenir_fournisseur", side_effect=AssertionError("appel IA interdit")):
            reponse = self.api_a.get(f"/api/rapports/{rapport_id}/pdf/")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["Content-Type"], "application/pdf")
        self.assertTrue(reponse.content.startswith(b"%PDF-"))
        self.assertIn("brouillon", reponse["Content-Disposition"])
        self.assertFalse(Rapport.objects.get(pk=rapport_id).fichier_pdf)  # aperçu jamais stocké
        self.assertTrue(JournalAudit.objects.filter(action="export", objet_id=rapport_id).exists())

    def test_edition_puis_validation_par_decisionnaire(self):
        rapport_id = self.generer(self.api_a, Factice()).data["id"]
        url = f"/api/rapports/{rapport_id}/"
        r = self.api_a.patch(url, {"sections": [{"cle": "synthese", "texte": "Relu : 42 mesures à reprendre."}]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        synthese = next(s for s in r.data["sections"] if s["cle"] == "synthese")
        self.assertEqual((synthese["source"], synthese["alertes"]), ("modifie", ["42"]))
        self.assertEqual(self.api_a.patch(url, {"sections": [{"cle": "x", "texte": "y"}]}, format="json").status_code, 400)

        self.assertEqual(self.api_a.post(f"{url}valider/").status_code, 403)  # chef de projet : pas décisionnaire
        r = self.api_admin.post(f"{url}valider/")
        self.assertEqual(r.status_code, 200, r.content)
        rapport = Rapport.objects.get(pk=rapport_id)
        with rapport.fichier_pdf.open("rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), rapport.sha256_pdf)
        self.assertEqual(self.api_admin.post(f"{url}valider/").status_code, 409)
        self.assertEqual(self.api_a.patch(url, {"sections": [{"cle": "synthese", "texte": "Après coup"}]}, format="json").status_code, 409)
        telecharge = self.api_a.get(f"{url}pdf/")
        self.assertEqual(hashlib.sha256(telecharge.content).hexdigest(), rapport.sha256_pdf)  # PDF figé servi tel quel

        StatutMesure.objects.filter(projet=self.projet).update(statut="conforme")
        v2 = Rapport.objects.get(pk=self.generer(self.api_a, Factice()).data["id"])
        self.assertEqual((v2.version, v2.rapport_precedent_id), (2, rapport.pk))
        self.assertEqual(v2.donnees["evolution"]["conforme"], 1)
        self.assertEqual(v2.donnees["evolution"]["manquant"], -1)

    def test_isolation_entre_organisations(self):
        rapport_id = self.generer(self.api_a, Factice()).data["id"]
        url = f"/api/rapports/{rapport_id}/"
        self.assertEqual(self.api_b.get("/api/rapports/").data["count"], 0)
        for reponse in (self.api_b.get(url), self.api_b.get(f"{url}pdf/"), self.api_b.post(f"{url}valider/"),
                        self.api_b.patch(url, {"sections": [{"cle": "synthese", "texte": "x"}]}, format="json")):
            self.assertEqual(reponse.status_code, 404)
        self.assertEqual(self.generer(self.api_b, Factice()).status_code, 400)  # projet d'une autre organisation

    def test_annexe_ebios(self):
        from apps.ebios.models import CoupleSROV, ObjectifVise, RisqueEBIOS, ScenarioStrategique, SourceRisque

        self.projet.ebios_active = True
        self.projet.save()
        couple = CoupleSROV.objects.create(projet=self.projet, source=SourceRisque.objects.create(projet=self.projet, libelle="Cybercriminel"),
                                           objectif=ObjectifVise.objects.create(projet=self.projet, libelle="Rançon"),
                                           motivation=3, ressources=3, activite=3, pertinence=4, retenu=True,
                                           justification="Note interne confidentielle")
        ss = ScenarioStrategique.objects.create(projet=self.projet, couple=couple, intitule="Rançongiciel", gravite=4)
        RisqueEBIOS.objects.create(projet=self.projet, scenario_strategique=ss, intitule="Chiffrement des serveurs", gravite=4,
                                   vraisemblance=2, option_traitement="reduire")
        fournisseur = Scripte({"sections": [{"cle": "synthese", "texte": "Synthèse."}]})
        rapport = Rapport.objects.get(pk=self.generer(self.api_a, fournisseur).data["id"])
        ebios = rapport.donnees["ebios"]
        self.assertEqual((ebios["couples_retenus"], ebios["matrice"]), (["Cybercriminel → Rançon"], {"4-2": 1}))
        envoye = fournisseur.messages[0]
        self.assertIn("Chiffrement des serveurs", envoye)
        self.assertNotIn("Note interne confidentielle", envoye)  # saisies détaillées des ateliers non transmises
        pdf = self.api_a.get(f"/api/rapports/{rapport.id}/pdf/")
        self.assertEqual(pdf.status_code, 200)

    def test_auditeur_ne_genere_pas(self):
        from apps.comptes.models import Role
        from apps.core.tests import fabriques as f
        from apps.core.tests.test_api import role
        from apps.projets.models import ActeurProjet

        lecteur = f.utilisateur(self.org_a, "lecteur@a.test")
        ActeurProjet.objects.create(projet=self.projet, utilisateur=lecteur, role=role(Role.Portee.PROJET, "auditeur"))
        client = self.client_pour(lecteur)
        self.assertEqual(self.generer(client, Factice()).status_code, 403)
        rapport_id = self.generer(self.api_a, Factice()).data["id"]
        self.assertEqual(client.get(f"/api/rapports/{rapport_id}/pdf/").status_code, 200)  # lecture autorisée


class OutilsTests(BaseApi):
    def test_chaine_css_neutralisee(self):
        self.assertEqual(chaine_css('Projet "x"; } </style><script>'), 'Projet \\"x\\"; }  /style  script ')

    def test_chiffres_non_verifies(self):
        donnees = {"a": 12, "b": [1, 2, 3], "c": {"taux": 38}}
        self.assertEqual(chiffres_non_verifies("12 mesures, 38 %, 3 points, 2026, 99 écarts, 8 axes et M12", donnees), ["8", "99"])
