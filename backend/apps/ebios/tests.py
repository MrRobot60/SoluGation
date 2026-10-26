"""EBIOS RM : isolation entre organisations et entre projets (y compris les relations multiples), méthode
activable par projet, cohérence entre ateliers, passage de l'atelier 5 au plan d'action et au registre des
risques résiduels, socle pré-rempli depuis la conformité."""

from apps.comptes.models import Role
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role
from apps.projets.models import ActeurProjet, StatutMesure
from apps.referentiels.models import Mesure
from apps.risques.models import RisqueResiduel
from apps.suivi.models import Tache

from .models import EcartSocle, MesureTraitement

API = "/api/ebios"


class EbiosTests(BaseApi):
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
