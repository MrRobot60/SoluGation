"""Double authentification : connexion en deux temps, anti-rejeu, codes de secours, politique de l'installation
appliquée côté serveur (API et admin Django), réinitialisation par l'administrateur, isolation."""

from datetime import timedelta
from unittest import mock

import pyotp
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import JournalAudit
from apps.comptes.models import ConfigurationSecurite, Role
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role

MDP = "mot-de-passe-de-test-1"


@override_settings(MAILS_COMPTES_SYNCHRONES=True, DOUBLE_AUTH_POLITIQUE="facultative")
class DoubleAuthTests(BaseApi):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.session = self.connecter("chef@a.test")

    def connecter(self, email, mdp=MDP):
        client = APIClient()
        r = client.post("/api/auth/connexion/", {"email": email, "password": mdp}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return client

    def activer(self, client=None):
        client = client or self.session
        r = client.post("/api/auth/double-auth/preparer/", {"mot_de_passe": MDP}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        secret = r.data["secret"]
        self.assertIn("<svg", r.data["qr_svg"])
        self.assertTrue(r.data["uri"].startswith("otpauth://totp/SoluGation:"))
        with self.captureOnCommitCallbacks(execute=True):
            r = client.post("/api/auth/double-auth/activer/", {"code": pyotp.TOTP(secret).now()}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data["codes_secours"]), 10)
        return pyotp.TOTP(secret), r.data["codes_secours"]

    def code_de(self, totp, decalage):
        return totp.at(timezone.now() + timedelta(seconds=30 * decalage))

    def test_activation_puis_connexion_en_deux_temps(self):
        autre = self.connecter("chef@a.test")
        mauvais = self.session.post("/api/auth/double-auth/preparer/", {"mot_de_passe": "faux"}, format="json")
        self.assertEqual(mauvais.status_code, 400)  # mot de passe redemandé
        totp, _ = self.activer()
        self.assertIn("activée", mail.outbox[-1].subject)
        self.assertEqual(self.session.get("/api/auth/moi/").status_code, 200)  # la session qui active reste ouverte
        self.assertEqual(autre.get("/api/auth/moi/").status_code, 403)  # les autres sont fermées
        self.assertTrue(self.session.get("/api/auth/moi/").data["double_auth"]["active"])

        client = APIClient()
        r = client.post("/api/auth/connexion/", {"email": "chef@a.test", "password": MDP}, format="json")
        self.assertEqual(r.data, {"double_authentification": True})
        self.assertEqual(client.get("/api/auth/moi/").status_code, 403)  # pas encore connecté
        self.assertEqual(client.post("/api/auth/connexion/code/", {"code": "000000"}, format="json").status_code, 400)
        code = self.code_de(totp, 1)
        r = client.post("/api/auth/connexion/code/", {"code": code}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(client.get("/api/projets/").status_code, 200)
        entree = JournalAudit.objects.filter(action=JournalAudit.Action.CONNEXION, objet_id=str(self.user_a.pk)).latest("horodatage")
        self.assertEqual(entree.donnees, {"double_authentification": "application"})

        # Anti-rejeu : le même code, intercepté, ne rouvre pas de session.
        pirate = APIClient()
        pirate.post("/api/auth/connexion/", {"email": "chef@a.test", "password": MDP}, format="json")
        self.assertEqual(pirate.post("/api/auth/connexion/code/", {"code": code}, format="json").status_code, 400)

    def test_code_de_secours_usage_unique(self):
        _, codes = self.activer()
        for attendu in (200, 400):
            client = APIClient()
            client.post("/api/auth/connexion/", {"email": "chef@a.test", "password": MDP}, format="json")
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(client.post("/api/auth/connexion/code/", {"code": codes[0].upper()}, format="json").status_code, attendu)
        self.assertIn("secours", mail.outbox[-1].subject)
        self.assertEqual(self.session.get("/api/auth/double-auth/").data["codes_secours_restants"], 9)

    def test_essais_et_delai_limites(self):
        totp, _ = self.activer()
        client = APIClient()
        client.post("/api/auth/connexion/", {"email": "chef@a.test", "password": MDP}, format="json")
        for _ in range(5):
            client.post("/api/auth/connexion/code/", {"code": "123456"}, format="json")
        r = client.post("/api/auth/connexion/code/", {"code": self.code_de(totp, 1)}, format="json")
        self.assertEqual(r.status_code, 400)  # 5 échecs : il faut redonner le mot de passe
        self.assertIn("reconnectez-vous", r.data["detail"])

        client.post("/api/auth/connexion/", {"email": "chef@a.test", "password": MDP}, format="json")
        with mock.patch("apps.comptes.api_double_auth.time.time", return_value=timezone.now().timestamp() + 600):
            self.assertEqual(client.post("/api/auth/connexion/code/", {"code": self.code_de(totp, 1)}, format="json").status_code, 400)

    def test_code_sans_mot_de_passe_refuse(self):
        self.activer()
        self.assertEqual(APIClient().post("/api/auth/connexion/code/", {"code": "123456"}, format="json").status_code, 400)

    def test_desactivation_et_codes_regeneres(self):
        _, anciens = self.activer()
        r = self.session.post("/api/auth/double-auth/codes-secours/", {"mot_de_passe": MDP}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(set(r.data["codes_secours"]).isdisjoint(anciens))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.session.post("/api/auth/double-auth/desactiver/", {"mot_de_passe": MDP}, format="json").status_code, 200)
        self.connecter("chef@a.test")  # de nouveau un seul facteur

    def test_politique_tous_imposee_cote_serveur(self):
        ConfigurationSecurite.objects.create(politique_double_auth="tous")
        r = self.session.get("/api/projets/")
        self.assertEqual((r.status_code, r.json()["code"]), (403, "double_auth_a_configurer"))
        self.assertEqual(self.session.get("/api/auth/moi/").data["double_auth"], {"politique": "tous", "requise": True, "active": False})
        self.activer()
        self.assertEqual(self.session.get("/api/projets/").status_code, 200)
        self.assertEqual(self.session.post("/api/auth/double-auth/desactiver/", {"mot_de_passe": MDP}, format="json").status_code, 400)

    def test_politique_administrateurs(self):
        ConfigurationSecurite.objects.create(politique_double_auth="administrateurs")
        self.assertEqual(self.session.get("/api/projets/").status_code, 200)  # simple membre
        admin = self.connecter("admin@a.test")
        self.assertEqual(admin.get("/api/projets/").status_code, 403)

    @override_settings(DOUBLE_AUTH_POLITIQUE="desactivee")
    def test_politique_desactivee(self):
        self.assertEqual(self.session.post("/api/auth/double-auth/preparer/", {"mot_de_passe": MDP}, format="json").status_code, 400)

    def test_reinitialisation_par_l_administrateur_et_isolation(self):
        totp, _ = self.activer()
        admin_b = f.utilisateur(self.org_b, "admin@b.test")
        admin_b.role = role(Role.Portee.ORGANISATION, "admin")
        admin_b.save()
        api_b = self.connecter("admin@b.test")
        url = f"/api/administration/comptes/{self.user_a.pk}/reinitialiser-double-auth/"
        self.assertEqual(api_b.post(url).status_code, 404)  # autre organisation
        self.assertEqual(self.session.post(url).status_code, 403)  # simple membre
        admin = self.connecter("admin@a.test")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(admin.post(url).status_code, 204)
        self.assertIn("réinitialisée", mail.outbox[-1].subject)
        self.connecter("chef@a.test")  # mot de passe seul

    def test_admin_django_ne_contourne_pas(self):
        racine = f.utilisateur(self.org_a, "root@a.test")
        racine.is_superuser = racine.is_staff = True
        racine.save()
        self.activer(self.connecter("root@a.test"))
        navigateur = self.client_class()
        navigateur.post("/admin/login/", {"username": "root@a.test", "password": MDP})
        r = navigateur.get("/admin/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].endswith("/connexion"))

    def test_politique_reservee_a_l_administrateur_de_l_installation(self):
        admin = self.connecter("admin@a.test")
        self.assertEqual(admin.get("/api/administration/securite/").status_code, 403)
        racine = f.utilisateur(self.org_a, "root@a.test")
        racine.is_superuser = racine.is_staff = True
        racine.save()
        api = self.connecter("root@a.test")
        r = api.patch("/api/administration/securite/", {"politique_double_auth": "administrateurs"}, format="json")
        self.assertEqual((r.status_code, r.data["politique"]), (200, "administrateurs"))
        entree = JournalAudit.objects.filter(objet_type__icontains="configurationsecurite").latest("horodatage")
        self.assertEqual(entree.donnees["politique_double_auth"], {"avant": "facultative", "apres": "administrateurs"})
        self.assertEqual(api.get("/api/administration/securite/").status_code, 403)  # elle s'applique aussitôt à lui-même
