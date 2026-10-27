"""Commandes d'installation : organisation et comptes créés sans mot de passe en argument."""

import os
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Organisation, Utilisateur


class CommandesComptesTests(TestCase):
    def appeler(self, *args, mot_de_passe="Une-phrase-de-passe-solide-2026"):
        with mock.patch.dict(os.environ, {"SOLUGATION_MOT_DE_PASSE": mot_de_passe}):
            call_command(*args, stdout=StringIO())

    def test_organisation_et_premier_administrateur(self):
        self.appeler("creer_organisation", "--nom", "Mairie de Lyon", "--email", "Rssi@Lyon.fr", "--admin-installation")
        org = Organisation.objects.get(slug="mairie-de-lyon")
        u = Utilisateur.objects.get(email="rssi@lyon.fr")
        self.assertEqual((u.organisation, u.role.code, u.is_superuser), (org, "admin", True))
        self.assertTrue(u.check_password("Une-phrase-de-passe-solide-2026"))
        with self.assertRaises(CommandError):
            self.appeler("creer_organisation", "--nom", "Autre", "--email", "rssi@lyon.fr")  # compte déjà pris

    def test_utilisateur_et_mot_de_passe_faible(self):
        self.appeler("creer_organisation", "--nom", "Cabinet", "--email", "admin@cabinet.fr")
        self.appeler("creer_utilisateur", "--organisation", "cabinet", "--email", "audit@cabinet.fr", "--role", "auditeur")
        self.assertTrue(Utilisateur.objects.get(email="audit@cabinet.fr").est_lecture_seule)
        with self.assertRaises(CommandError):
            self.appeler("creer_utilisateur", "--organisation", "cabinet", "--email", "x@cabinet.fr", mot_de_passe="123")
        with self.assertRaises(CommandError):
            self.appeler("creer_utilisateur", "--organisation", "inconnue", "--email", "y@cabinet.fr")
