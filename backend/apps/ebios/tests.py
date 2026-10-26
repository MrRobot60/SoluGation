"""EBIOS RM : isolation entre organisations et entre projets (y compris les relations multiples), méthode
activable par projet, cohérence entre ateliers, passage de l'atelier 5 au plan d'action et au registre des
risques résiduels, socle pré-rempli depuis la conformité."""

from unittest import mock

from django.test import override_settings

from apps.ai.provider import Factice, ReponseIA
from apps.comptes.models import Role
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role
from apps.projets.models import ActeurProjet, StatutMesure
from apps.referentiels.models import Mesure
from apps.risques.models import RisqueResiduel
from apps.suivi.models import Tache

from .models import (
    BienSupport, CoupleSROV, EcartSocle, EvenementRedoute, MesureTraitement, ScenarioOperationnel, ScenarioStrategique,
    SuggestionEBIOS,
)

API = "/api/ebios"


class EbiosBase(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet = self.creer_projet(self.api_a, "Projet A", ebios_active=True)
        self.autre = self.creer_projet(self.api_a, "Projet A2", ebios_active=True)
        self.projet_b = self.creer_projet(self.api_b, "Projet B", ebios_active=True)

    def creer(self, client, ressource, projet=None, **donnees):
        reponse = client.post(f"{API}/{ressource}/", {"projet": str((projet or self.projet).id), **donnees}, format="json")
        return reponse

    def ok(self, ressource, projet=None, client=None, **donnees):
        reponse = self.creer(client or self.api_a, ressource, projet, **donnees)
        self.assertEqual(reponse.status_code, 201, reponse.content)
        return reponse.data["id"]

    def chaine(self, projet=None):
        """Valeur métier → événement redouté, SR/OV retenu → scénario stratégique → chemin → scénario opérationnel."""
        vm = self.ok("valeurs-metier", projet, nom="Dossiers usagers", nature="information")
        er = self.ok("evenements-redoutes", projet, valeur_metier=vm, description="Fuite des dossiers", gravite=4)
        sr = self.ok("sources-risque", projet, libelle="Cybercriminel")
        ov = self.ok("objectifs-vises", projet, libelle="Revente de données")
        couple = self.ok("couples", projet, source=sr, objectif=ov, motivation=3, ressources=3, activite=3, pertinence=4, retenu=True)
        ss = self.ok("scenarios-strategiques", projet, couple=couple, intitule="Exfiltration des dossiers", gravite=4,
                     evenements_redoutes=[er])
        chemin = self.ok("chemins", projet, scenario=ss, description="Via le prestataire d'infogérance")
        so = self.ok("scenarios-operationnels", projet, chemin=chemin, intitule="Hameçonnage puis rebond", vraisemblance=3)
        return {"vm": vm, "er": er, "couple": couple, "ss": ss, "chemin": chemin, "so": so}


class EbiosTests(EbiosBase):
    def test_isolation_entre_organisations(self):
        vm = self.ok("valeurs-metier", nom="Paie", nature="processus")
        self.assertEqual(self.api_b.get(f"{API}/valeurs-metier/").data["count"], 0)
        self.assertEqual(self.api_b.get(f"{API}/valeurs-metier/{vm}/").status_code, 404)
        self.assertEqual(self.api_b.patch(f"{API}/valeurs-metier/{vm}/", {"nom": "x"}, format="json").status_code, 404)
        self.assertEqual(self.api_b.delete(f"{API}/valeurs-metier/{vm}/").status_code, 404)
        self.assertEqual(self.creer(self.api_b, "valeurs-metier", self.projet, nom="x", nature="processus").status_code, 400)
        # Relation multiple vers un objet d'une autre organisation : refusée.
        r = self.creer(self.api_b, "biens-supports", self.projet_b, nom="Serveur", valeurs_metier=[vm])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.api_b.get(f"{API}/synthese/?projet={self.projet.id}").status_code, 404)

    def test_relations_multiples_limitees_au_projet(self):
        vm_autre = self.ok("valeurs-metier", self.autre, nom="Autre", nature="processus")
        self.assertEqual(self.creer(self.api_a, "biens-supports", nom="Serveur", valeurs_metier=[vm_autre]).status_code, 400)
        c = self.chaine(self.autre)
        couple = self.chaine()["couple"]
        r = self.creer(self.api_a, "scenarios-strategiques", couple=couple, intitule="x", gravite=2, evenements_redoutes=[c["er"]])
        self.assertEqual(r.status_code, 400)
        acteur_autre = ActeurProjet.objects.filter(projet=self.autre).first()
        atelier = self.api_a.get(f"{API}/ateliers/?projet={self.projet.id}").data["results"][0]["id"]
        r = self.api_a.patch(f"{API}/ateliers/{atelier}/", {"participants": [str(acteur_autre.id)]}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_methode_activable_par_projet(self):
        sans = self.creer_projet(self.api_a, "Sans EBIOS")
        self.assertEqual(self.creer(self.api_a, "valeurs-metier", sans, nom="x", nature="processus").status_code, 400)
        self.assertEqual(self.api_a.get(f"{API}/synthese/?projet={sans.id}").status_code, 403)

    def test_coherence_entre_ateliers(self):
        c = self.chaine()
        sr = self.ok("sources-risque", libelle="Hacktiviste")
        ov = self.ok("objectifs-vises", libelle="Défiguration")
        non_retenu = self.ok("couples", source=sr, objectif=ov, motivation=1, ressources=1, activite=1, pertinence=1)
        self.assertEqual(self.creer(self.api_a, "scenarios-strategiques", couple=non_retenu, intitule="x", gravite=1).status_code, 400)

        risque = self.creer(self.api_a, "risques", scenario_strategique=c["ss"], scenario_operationnel=c["so"], intitule="R1")
        self.assertEqual(risque.status_code, 201, risque.content)
        self.assertEqual((risque.data["gravite"], risque.data["vraisemblance"], risque.data["niveau"]), (4, 3, 12))
        autre_ss = self.ok("scenarios-strategiques", couple=c["couple"], intitule="Rançongiciel", gravite=3)
        r = self.creer(self.api_a, "risques", scenario_strategique=autre_ss, scenario_operationnel=c["so"], intitule="R2")
        self.assertEqual(r.status_code, 400)  # le scénario opérationnel découle d'un autre scénario stratégique
        self.assertEqual(self.creer(self.api_a, "risques", scenario_strategique=autre_ss, intitule="R3").status_code, 400)

    def test_atelier_5_vers_plan_action_et_registre(self):
        c = self.chaine()
        risque = self.creer(self.api_a, "risques", scenario_strategique=c["ss"], scenario_operationnel=c["so"],
                            intitule="Exfiltration", option_traitement="accepter").data
        residuel = RisqueResiduel.objects.get(risque_ebios_id=risque["id"])
        self.assertEqual((residuel.origine, residuel.gravite, residuel.vraisemblance, residuel.statut), ("ebios", 4, 3, "identifie"))
        self.api_a.patch(f"{API}/risques/{risque['id']}/", {"option_traitement": "reduire", "gravite_residuelle": 4,
                                                            "vraisemblance_residuelle": 1}, format="json")
        self.assertFalse(RisqueResiduel.objects.filter(risque_ebios_id=risque["id"]).exists())

        mesure = self.ok("mesures-traitement", intitule="Imposer l'authentification forte au prestataire", risques=[risque["id"]])
        tache = MesureTraitement.objects.get(pk=mesure).tache
        self.assertEqual((tache.origine, tache.statut, tache.projet_id), (Tache.Origine.EBIOS, "a_faire", self.projet.id))
        self.assertIn("Exfiltration", tache.description)

    def test_socle_prerempli_depuis_la_conformite(self):
        m2 = Mesure.objects.create(referentiel=self.rgs, identifiant="§2.2", intitule="Journalisation")
        StatutMesure.objects.create(projet=self.projet, mesure=self.mesure_rgs, statut="manquant", justification="Absente")
        StatutMesure.objects.create(projet=self.projet, mesure=m2, statut="partiel")
        r = self.api_a.post(f"{API}/socle/", {"projet": str(self.projet.id)}, format="json")
        self.assertEqual(r.data["crees"], 2)
        self.assertEqual(EcartSocle.objects.get(projet=self.projet, mesure=self.mesure_rgs).etat, "non_applique")
        self.assertEqual(self.api_a.post(f"{API}/socle/", {"projet": str(self.projet.id)}, format="json").data["crees"], 0)
        hors = Mesure.objects.get(referentiel=self.hygiene)  # référentiel non retenu pour le projet
        self.assertEqual(self.creer(self.api_a, "ecarts-socle", mesure=str(hors.id), intitule="x", etat="applique").status_code, 400)

    def test_synthese(self):
        self.assertEqual(len(self.api_a.get(f"{API}/ateliers/?projet={self.projet.id}").data["results"]), 5)
        c = self.chaine()
        self.ok("parties-prenantes", nom="Infogérant", dependance=4, penetration=4, maturite=2, confiance=2)
        self.ok("risques", scenario_strategique=c["ss"], scenario_operationnel=c["so"], intitule="R1")
        s = self.api_a.get(f"{API}/synthese/?projet={self.projet.id}").data
        self.assertEqual(s["comptes"]["risques"], 1)
        self.assertEqual(s["matrice"]["initiale"]["4-3"][0]["intitule"], "R1")
        self.assertEqual(s["cartographie"]["parties"][0]["zone"], "danger")  # 16 / 4 = 4
        self.assertIn("1 risque(s) sans option de traitement.", [a["texte"] for a in s["alertes"]])

    def test_auditeur_en_lecture_seule(self):
        lecteur = f.utilisateur(self.org_a, "lecteur@a.test")
        ActeurProjet.objects.create(projet=self.projet, utilisateur=lecteur, role=role(Role.Portee.PROJET, "auditeur"))
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_login(lecteur)
        self.assertEqual(self.creer(client, "valeurs-metier", nom="x", nature="processus").status_code, 403)
        self.assertEqual(client.get(f"{API}/synthese/?projet={self.projet.id}").status_code, 200)
        self.assertEqual(client.post(f"{API}/socle/", {"projet": str(self.projet.id)}, format="json").status_code, 403)


class Scripte:
    nom, modele = "scripte", "v0"

    def __init__(self, contenu):
        self.contenu, self.messages = contenu, []

    def verifier_configuration(self):
        pass

    def completer_json(self, systeme, utilisateur):
        self.messages.append((systeme, utilisateur))
        return ReponseIA(self.contenu, 10, 10)


@override_settings(IA_SYNCHRONE=True)
class SuggestionTests(EbiosBase):
    """Propositions de l'IA : contexte sans nom, clés vérifiées, rien de créé sans décision humaine."""

    def demander(self, client, fournisseur, atelier, projet=None, **extra):
        with mock.patch("apps.ai.analyse.obtenir_fournisseur", return_value=fournisseur), \
             self.captureOnCommitCallbacks(execute=True):
            return client.post(f"{API}/suggestions/demander/", {"projet": str((projet or self.projet).id), "atelier": atelier, **extra},
                               format="json")

    def statuer(self, suggestion, decision="valide", client=None, **extra):
        return (client or self.api_a).post(f"{API}/suggestions/{suggestion.id}/statuer/", {"decision": decision, **extra}, format="json")

    def test_atelier_1_evenements_et_biens(self):
        vm = self.ok("valeurs-metier", nom="Dossiers usagers", nature="information", entite_responsable="Mme Dupont")
        fournisseur = Scripte({"propositions": [
            {"cible": "VM1", "evenements_redoutes": [{"description": "Divulgation des dossiers", "impacts": "Atteinte à la vie privée", "gravite": 9}],
             "biens_supports": [{"nom": "Base de données", "type_bien": "serveur"}]},
            {"cible": "VM9", "evenements_redoutes": [{"description": "Inventé"}]},  # clé inconnue : écartée
        ]})
        self.assertEqual(self.demander(self.api_a, fournisseur, 1).status_code, 202)
        systeme, message = fournisseur.messages[0]
        self.assertIn("Atelier 1", systeme)
        self.assertNotIn("Dupont", message)  # entité responsable jamais transmise
        suggestions = {s.type_objet: s for s in SuggestionEBIOS.objects.filter(projet=self.projet)}
        self.assertEqual(set(suggestions), {"evenement_redoute", "bien_support"})
        self.assertEqual(suggestions["evenement_redoute"].contenu["gravite"], 4)  # cotation bornée
        self.assertFalse(EvenementRedoute.objects.exists())  # rien de créé avant décision
        self.assertEqual(self.demander(self.api_a, fournisseur, 1).status_code, 400)  # propositions en attente

        corrige = {**suggestions["evenement_redoute"].contenu, "gravite": 3}
        self.assertEqual(self.statuer(suggestions["evenement_redoute"], contenu=corrige).status_code, 200)
        er = EvenementRedoute.objects.get(projet=self.projet)
        self.assertEqual((str(er.valeur_metier_id), er.gravite), (vm, 3))
        self.statuer(suggestions["bien_support"])
        self.assertEqual(list(BienSupport.objects.get(projet=self.projet).valeurs_metier.values_list("nom", flat=True)), ["Dossiers usagers"])
        self.assertEqual(self.statuer(suggestions["bien_support"]).status_code, 409)

    def test_atelier_2_couples_jamais_retenus_d_office(self):
        c = self.chaine()
        fournisseur = Scripte({"propositions": [
            {"source": {"libelle": "Cybercriminel"}, "objectif": {"libelle": "Revente de données"}},  # existe déjà
            {"source": {"libelle": "Hacktiviste", "categorie": "hacktiviste"}, "objectif": {"libelle": "Défiguration"},
             "motivation": 2, "ressources": 1, "activite": 2, "pertinence": 2, "justification": "Visibilité du portail."},
        ]})
        self.demander(self.api_a, fournisseur, 2)
        suggestion = SuggestionEBIOS.objects.get(projet=self.projet, atelier=2)
        self.statuer(suggestion)
        couple = CoupleSROV.objects.exclude(pk=c["couple"]).get(projet=self.projet)
        self.assertEqual((couple.source.libelle, couple.retenu), ("Hacktiviste", False))

    def test_ateliers_3_et_4_scenarios(self):
        self.assertEqual(self.demander(self.api_a, Scripte({}), 3).status_code, 400)  # aucun couple retenu
        vm = self.ok("valeurs-metier", nom="Paie", nature="processus")
        self.ok("evenements-redoutes", valeur_metier=vm, description="Paie bloquée", gravite=3)
        self.ok("parties-prenantes", nom="Infogérant", dependance=3, penetration=3, maturite=2, confiance=2)
        self.ok("biens-supports", nom="Serveur de paie")
        sr = self.ok("sources-risque", libelle="Cybercriminel")
        ov = self.ok("objectifs-vises", libelle="Rançon")
        self.ok("couples", source=sr, objectif=ov, motivation=3, ressources=3, activite=3, pertinence=4, retenu=True)
        self.demander(self.api_a, Scripte({"propositions": [{
            "cible": "C1", "intitule": "Rançongiciel via l'infogérant", "evenements_redoutes": ["ER1", "ER9"], "gravite": 3,
            "chemins": [{"description": "Compromission du poste d'administration de l'infogérant", "parties_prenantes": ["PP1", "PP7"]}],
        }]}), 3)
        self.statuer(SuggestionEBIOS.objects.get(projet=self.projet, atelier=3))
        ss = ScenarioStrategique.objects.get(projet=self.projet)
        self.assertEqual(ss.evenements_redoutes.count(), 1)  # ER9 inconnu : ignoré
        chemin = ss.chemins.get()
        self.assertEqual(list(chemin.parties_prenantes.values_list("nom", flat=True)), ["Infogérant"])

        self.demander(self.api_a, Scripte({"propositions": [{"cible": "CH1", "intitule": "Hameçonnage de l'administrateur",
                                                             "mode_operatoire": "1. Reconnaissance", "biens_supports": ["BS1"],
                                                             "vraisemblance": 3}]}), 4)
        self.statuer(SuggestionEBIOS.objects.get(projet=self.projet, atelier=4))
        so = ScenarioOperationnel.objects.get(projet=self.projet)
        self.assertEqual((so.chemin_id, so.vraisemblance, so.biens_supports.count()), (chemin.pk, 3, 1))

    def test_isolation_et_ia_desactivee(self):
        self.ok("valeurs-metier", nom="Paie", nature="processus")
        fournisseur = Factice()
        self.demander(self.api_a, fournisseur, 1)
        suggestion = SuggestionEBIOS.objects.filter(projet=self.projet).first()
        self.assertEqual(self.api_b.get(f"{API}/suggestions/{suggestion.id}/").status_code, 404)
        self.assertEqual(self.statuer(suggestion, client=self.api_b).status_code, 404)
        self.assertEqual(self.api_b.get(f"{API}/suggestions/").data["count"], 0)
        self.assertEqual(self.demander(self.api_b, fournisseur, 2, self.projet).status_code, 400)
        self.org_a.ia_activee = False
        self.org_a.save()
        self.assertEqual(self.demander(self.api_a, fournisseur, 2).status_code, 403)

    def test_parent_supprime(self):
        vm = self.ok("valeurs-metier", nom="Paie", nature="processus")
        self.demander(self.api_a, Factice(), 1)
        self.api_a.delete(f"{API}/valeurs-metier/{vm}/")
        suggestion = SuggestionEBIOS.objects.filter(projet=self.projet, type_objet="evenement_redoute").first()
        self.assertEqual(self.statuer(suggestion).status_code, 400)
        self.assertEqual(SuggestionEBIOS.objects.get(pk=suggestion.pk).statut_validation, "a_valider")
