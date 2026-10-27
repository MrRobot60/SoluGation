"""Administration de l'IA : réservée à l'administrateur de l'installation, clé chiffrée et jamais renvoyée,
responsabilité acceptée explicitement, protection SSRF (à l'enregistrement et à chaque appel), priorité de
l'écran sur le fichier, et produit entièrement utilisable sans IA."""

import io
import json
import socket
from unittest import mock

from django.test import override_settings
from rest_framework.test import APIClient

from apps.audit.models import JournalAudit
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi

from .models import ConfigurationIA
from .provider import CompatibleOpenAI, Factice, IAIndisponible, _SansRedirection, obtenir_fournisseur

URL = "/api/administration/ia/"
CLE = "sk-test-0123456789abcdef"


def adresse(ip):
    return mock.patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))])


def reponse_json(contenu):
    r = mock.MagicMock()
    r.__enter__.return_value = io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps(contenu)}}]}).encode())
    return r


@override_settings(IA_FOURNISSEUR="aucun", IA_AUTORISER_RESEAU_LOCAL=False)
class AdministrationIATests(BaseApi):
    def setUp(self):
        super().setUp()
        self.root = f.utilisateur(self.org_a, "root@a.test")
        self.root.is_superuser = True
        self.root.save()
        self.api_root = APIClient()
        self.api_root.force_login(self.root)
        self.api_admin_org = APIClient()
        self.api_admin_org.force_login(self.admin_a)

    def configurer(self, **donnees):
        with adresse("51.159.1.10"):
            return self.api_root.put(URL, {"nom": "Fournisseur", "url": "https://api.exemple.eu/v1", "modele": "petit-modele",
                                           "cle": CLE, **donnees}, format="json")

    def test_sans_ia_tout_fonctionne(self):
        self.assertFalse(self.api_a.get("/api/auth/moi/").data["ia_disponible"])
        with self.assertRaisesMessage(IAIndisponible, "Aucune IA"):
            obtenir_fournisseur()
        projet = self.creer_projet(self.api_a)
        self.deposer(self.api_a, projet, contenu=b"Politique de securite du systeme d'information." * 3, nom="pssi.txt")
        self.assertEqual(self.api_a.post("/api/analyses-ia/", {"projet": str(projet.id)}, format="json").status_code, 503)
        rapport = self.api_a.post("/api/rapports/", {"projet": str(projet.id)}, format="json")
        self.assertEqual(rapport.status_code, 201)  # rapport toujours générable : texte automatique
        self.assertEqual({s["source"] for s in rapport.data["sections"]}, {"automatique"})

    def test_reserve_a_l_administrateur_de_l_installation(self):
        for client in (self.api_a, self.api_admin_org, self.api_b):
            self.assertEqual(client.get(URL).status_code, 403)
            self.assertEqual(client.put(URL, {"url": "https://x.eu/v1"}, format="json").status_code, 403)
            self.assertEqual(client.post(f"{URL}tester/").status_code, 403)

    def test_cle_chiffree_et_jamais_renvoyee(self):
        r = self.configurer()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn(CLE, json.dumps(r.data, default=str))
        self.assertEqual((r.data["ecran"]["a_une_cle"], r.data["ecran"]["cle_fin"]), (True, "cdef"))
        stockee = ConfigurationIA.courante().cle_chiffree
        self.assertNotIn(CLE, stockee)
        self.assertNotIn(CLE, json.dumps(self.api_root.get(URL).data, default=str))
        # Clé absente de la requête suivante : conservée.
        with adresse("51.159.1.10"):
            self.api_root.put(URL, {"nom": "Autre nom"}, format="json")
        self.assertEqual(ConfigurationIA.courante().cle_chiffree, stockee)

    def test_activation_exige_l_acceptation_de_responsabilite(self):
        r = self.configurer(actif=True)
        self.assertEqual(r.status_code, 400)
        self.assertIn("accepter_responsabilite", r.data)
        r = self.configurer(actif=True, accepter_responsabilite=True)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["source"], "ecran")
        self.assertTrue(self.api_a.get("/api/auth/moi/").data["ia_disponible"])
        self.assertTrue(JournalAudit.objects.filter(objet_type="ai.ConfigurationIA").exists())
        # L'organisation peut toujours couper l'IA pour elle-même.
        self.org_a.ia_activee = False
        self.org_a.save()
        self.assertFalse(self.api_a.get("/api/auth/moi/").data["ia_disponible"])

    def test_changement_de_fournisseur_redemande_la_responsabilite(self):
        self.configurer(actif=True, accepter_responsabilite=True)
        with adresse("51.159.1.11"):
            r = self.api_root.put(URL, {"url": "https://autre.exemple.eu/v1"}, format="json")
        self.assertEqual((r.data["ecran"]["actif"], r.data["ecran"]["responsabilite_acceptee_le"]), (False, None))
        with adresse("51.159.1.11"):
            r = self.api_root.put(URL, {"nom": "Renommé seulement"}, format="json")  # changement cosmétique : sans effet
        self.assertEqual(r.data["ecran"]["nom"], "Renommé seulement")

    def test_ssrf_refusee_a_l_enregistrement(self):
        for ip in ("169.254.169.254", "10.0.0.5", "127.0.0.1", "192.168.1.20", "::1"):
            with self.subTest(ip=ip), adresse(ip):
                r = self.api_root.put(URL, {"url": "https://interne.exemple/v1"}, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn("url", r.data)
        with adresse("51.159.1.10"):
            self.assertEqual(self.api_root.put(URL, {"url": "http://api.exemple.eu/v1"}, format="json").status_code, 400)
            self.assertEqual(self.api_root.put(URL, {"url": "https://u:p@api.exemple.eu/v1"}, format="json").status_code, 400)
        with override_settings(IA_AUTORISER_RESEAU_LOCAL=True):
            self.assertEqual(self.api_root.put(URL, {"url": "http://ollama:11434/v1"}, format="json").status_code, 200)

    def test_ssrf_controlee_a_chaque_appel_et_sans_redirection(self):
        self.configurer(actif=True, accepter_responsabilite=True)
        fournisseur = obtenir_fournisseur()
        self.assertIsInstance(fournisseur, CompatibleOpenAI)
        with adresse("169.254.169.254"), mock.patch("apps.ai.provider.OUVREUR.open") as envoi:  # le DNS a changé
            with self.assertRaises(IAIndisponible):
                fournisseur.completer_json("s", "u")
        envoi.assert_not_called()
        self.assertIsNone(_SansRedirection().redirect_request(None, None, 302, "", {}, "http://169.254.169.254/"))

    @override_settings(IA_FOURNISSEUR="factice")
    def test_ecran_prime_sur_le_fichier(self):
        self.assertIsInstance(obtenir_fournisseur(), Factice)
        self.configurer(actif=True, accepter_responsabilite=True)
        fournisseur = obtenir_fournisseur()
        self.assertEqual((fournisseur.nom, fournisseur.modele, fournisseur.cle), ("Fournisseur", "petit-modele", CLE))
        with adresse("51.159.1.10"):
            self.api_root.put(URL, {"actif": False}, format="json")
        self.assertIsInstance(obtenir_fournisseur(), Factice)  # désactivé à l'écran : retour au fichier

    def test_tester_la_connexion(self):
        self.configurer()
        with adresse("51.159.1.10"), mock.patch("apps.ai.provider.OUVREUR.open", return_value=reponse_json({"ok": True})) as envoi:
            r = self.api_root.post(f"{URL}tester/")
        self.assertTrue(r.data["ok"], r.data)
        requete = envoi.call_args.args[0]
        self.assertEqual(requete.get_header("Authorization"), f"Bearer {CLE}")
        self.assertNotIn("projet", requete.data.decode())  # aucune donnée de projet envoyée
