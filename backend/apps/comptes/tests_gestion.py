"""Comptes : administration limitée à l'organisation, invitation et réinitialisation par liens à usage unique,
aucune énumération des comptes, sessions fermées après changement de mot de passe."""

import re
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.audit.models import JournalAudit
from apps.comptes.models import Role, Utilisateur
from apps.comptes.mots_de_passe import JetonReinitialisation
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role

MDP = "Une-phrase-de-passe-solide-2026"


@override_settings(MAILS_COMPTES_SYNCHRONES=True, FRONTEND_URL="https://solugation.test")
class GestionComptesTests(BaseApi):
    def setUp(self):
        super().setUp()
        cache.clear()  # limitation des demandes (par adresse IP) remise à zéro
        self.admin = APIClient()
        self.admin.force_login(self.admin_a)
        self.admin_b = f.utilisateur(self.org_b, "admin@b.test")
        self.admin_b.role = role(Role.Portee.ORGANISATION, "admin")
        self.admin_b.save()
        self.api_admin_b = APIClient()
        self.api_admin_b.force_login(self.admin_b)

    def inviter(self, email="nouveau@a.test", **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return self.admin.post("/api/administration/comptes/", {"email": email, "first_name": "Ada", "last_name": "Lovelace",
                                                                    "role": "membre", **extra}, format="json")

    def lien_du_mail(self, indice=-1):
        url = re.search(r"https://solugation\.test/(invitation|mot-de-passe/nouveau)#uid=([^&\s]+)&jeton=([^\s\"<]+)", mail.outbox[indice].body)
        self.assertIsNotNone(url, mail.outbox[indice].body)
        nature = "invitation" if url.group(1) == "invitation" else "reinitialisation"
        return {"nature": nature, "uid": url.group(2), "jeton": url.group(3)}

    def definir(self, lien, password=None):
        anonyme = APIClient()
        with self.captureOnCommitCallbacks(execute=True):
            return anonyme.post("/api/auth/lien/", {**lien, **({"password": password} if password else {})}, format="json")

    def connexion(self, email, password):
        return APIClient().post("/api/auth/connexion/", {"email": email, "password": password}, format="json").status_code

    def test_invitation_de_bout_en_bout(self):
        r = self.inviter()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["etat"], "invite")
        nouveau = Utilisateur.objects.get(email="nouveau@a.test")
        self.assertEqual((nouveau.organisation, nouveau.role.code, nouveau.has_usable_password()), (self.org_a, "membre", False))
        self.assertEqual(mail.outbox[-1].to, ["nouveau@a.test"])
        self.assertTrue(JournalAudit.objects.filter(objet_id=str(nouveau.pk), action=JournalAudit.Action.CREATION).exists())

        lien = self.lien_du_mail()
        self.assertEqual(self.definir(lien).data["email"], "nouveau@a.test")  # vérification seule
        self.assertEqual(self.definir(lien, "motdepasse").status_code, 400)  # trop faible
        self.assertEqual(self.definir(lien, MDP).status_code, 204)
        self.assertEqual(self.connexion("nouveau@a.test", MDP), 200)
        self.assertEqual(self.definir(lien, "Autre-phrase-de-passe-2026").status_code, 400)  # usage unique

    def test_renvoi_invalide_le_lien_precedent(self):
        self.inviter()
        ancien = self.lien_du_mail()
        nouveau = Utilisateur.objects.get(email="nouveau@a.test")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.admin.post(f"/api/administration/comptes/{nouveau.pk}/renvoyer-invitation/").status_code, 204)
        self.assertEqual(self.definir(ancien, MDP).status_code, 400)
        self.assertEqual(self.definir(self.lien_du_mail(), MDP).status_code, 204)

    def test_reserve_a_l_administrateur_et_isole(self):
        self.assertEqual(self.api_a.get("/api/administration/comptes/").status_code, 403)  # simple membre
        self.assertEqual(self.api_a.post("/api/administration/comptes/", {"email": "x@a.test", "role": "membre"}, format="json").status_code, 403)
        ids_b = {c["id"] for c in self.api_admin_b.get("/api/administration/comptes/").data}
        self.assertNotIn(str(self.user_a.pk), ids_b)
        self.assertEqual(self.api_admin_b.patch(f"/api/administration/comptes/{self.user_a.pk}/", {"is_active": False}, format="json").status_code, 404)
        self.assertEqual(self.api_admin_b.post(f"/api/administration/comptes/{self.user_a.pk}/renvoyer-invitation/").status_code, 404)
        self.assertEqual(self.admin.delete(f"/api/administration/comptes/{self.user_a.pk}/").status_code, 405)  # jamais de suppression

    def test_adresse_deja_prise_et_email_fige(self):
        self.assertEqual(self.inviter(email="CHEF@b.test".replace("b", "a")).status_code, 400)  # chef@a.test existe
        self.assertEqual(self.inviter(email="chef@b.test").status_code, 400)  # pris dans une autre organisation
        r = self.admin.patch(f"/api/administration/comptes/{self.user_a.pk}/", {"email": "autre@a.test"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_role_desactivation_et_garde_fous(self):
        r = self.admin.patch(f"/api/administration/comptes/{self.user_a.pk}/", {"role": "auditeur", "fonction": "Auditeur interne"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.user_a.refresh_from_db()
        self.assertTrue(self.user_a.est_lecture_seule)
        entree = JournalAudit.objects.filter(objet_id=str(self.user_a.pk), action=JournalAudit.Action.MODIFICATION).latest("horodatage")
        self.assertEqual(entree.donnees["role"], {"avant": None, "apres": "auditeur"})

        self.assertEqual(self.admin.patch(f"/api/administration/comptes/{self.user_a.pk}/", {"is_active": False}, format="json").status_code, 200)
        self.assertEqual(self.connexion("chef@a.test", "mot-de-passe-de-test-1"), 400)
        self.assertEqual(self.api_a.get("/api/auth/moi/").status_code, 403)  # session ouverte coupée

        moi = f"/api/administration/comptes/{self.admin_a.pk}/"
        self.assertEqual(self.admin.patch(moi, {"is_active": False}, format="json").status_code, 400)
        self.assertEqual(self.admin.patch(moi, {"role": "membre"}, format="json").status_code, 400)

    def test_dernier_administrateur_et_administrateur_installation(self):
        second = f.utilisateur(self.org_a, "admin2@a.test")
        second.role = role(Role.Portee.ORGANISATION, "admin")
        second.save()
        url = f"/api/administration/comptes/{second.pk}/"
        self.assertEqual(self.admin.patch(url, {"role": "membre"}, format="json").status_code, 200)  # il en reste un
        racine = f.utilisateur(self.org_a, "root@a.test")
        racine.is_superuser = racine.is_staff = True
        racine.save()
        self.assertEqual(self.admin.patch(f"/api/administration/comptes/{racine.pk}/", {"is_active": False}, format="json").status_code, 400)

    def test_mot_de_passe_oublie_sans_enumeration(self):
        anonyme = APIClient()
        with self.captureOnCommitCallbacks(execute=True):
            inconnu = anonyme.post("/api/auth/mot-de-passe-oublie/", {"email": "personne@a.test"}, format="json")
        self.assertEqual((inconnu.status_code, len(mail.outbox)), (204, 0))
        with self.captureOnCommitCallbacks(execute=True):
            connu = anonyme.post("/api/auth/mot-de-passe-oublie/", {"email": "Chef@A.test"}, format="json")
        self.assertEqual((connu.status_code, connu.content), (inconnu.status_code, inconnu.content))
        self.assertEqual(mail.outbox[-1].to, ["chef@a.test"])

        lien = self.lien_du_mail()
        self.assertEqual(lien["nature"], "reinitialisation")
        self.assertEqual(self.definir({**lien, "nature": "invitation"}, MDP).status_code, 400)  # mauvaise nature
        self.assertEqual(self.definir({**lien, "jeton": lien["jeton"][:-2] + "xx"}, MDP).status_code, 400)
        self.assertEqual(self.definir(lien, MDP).status_code, 204)
        self.assertIn("modifié", mail.outbox[-1].subject)  # confirmation envoyée
        self.assertEqual(self.api_a.get("/api/auth/moi/").status_code, 403)  # anciennes sessions fermées
        self.assertEqual(self.connexion("chef@a.test", MDP), 200)
        self.assertEqual(self.definir(lien, "Encore-une-phrase-solide-2026").status_code, 400)

    def test_lien_de_reinitialisation_expire_apres_une_heure(self):
        with self.captureOnCommitCallbacks(execute=True):
            APIClient().post("/api/auth/mot-de-passe-oublie/", {"email": "chef@a.test"}, format="json")
        lien = self.lien_du_mail()
        plus_tard = JetonReinitialisation()._now() + timedelta(minutes=61)
        with mock.patch.object(JetonReinitialisation, "_now", return_value=plus_tard):
            self.assertEqual(self.definir(lien, MDP).status_code, 400)
        self.assertEqual(self.definir(lien, MDP).status_code, 204)

    def test_compte_desactive_ou_invite(self):
        self.inviter()
        with self.captureOnCommitCallbacks(execute=True):
            APIClient().post("/api/auth/mot-de-passe-oublie/", {"email": "nouveau@a.test"}, format="json")
        self.assertEqual(self.lien_du_mail()["nature"], "invitation")  # invitation non acceptée : renvoyée

        self.user_a.is_active = False
        self.user_a.save()
        nb = len(mail.outbox)
        with self.captureOnCommitCallbacks(execute=True):
            APIClient().post("/api/auth/mot-de-passe-oublie/", {"email": "chef@a.test"}, format="json")
        self.assertEqual(len(mail.outbox), nb)  # compte désactivé : rien n'est envoyé
