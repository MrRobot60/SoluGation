"""Réunions : isolation, participants du projet uniquement, invitations iCalendar (une par destinataire, mises à
jour et annulation), compte rendu figé et diffusé, actions devenues tâches, rappel, calendrier, tableau de bord."""

from datetime import timedelta

from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comptes.models import Role
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role
from apps.projets.models import ActeurProjet

from .models import Reunion, Tache
from .reunions import rappeler_reunions

URL = "/api/reunions/"


class ReunionTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet = self.creer_projet(self.api_a, "Projet A")
        self.chef = ActeurProjet.objects.get(projet=self.projet, utilisateur=self.user_a)
        self.collegue = f.utilisateur(self.org_a, "rssi@a.test")
        self.acteur_rssi = ActeurProjet.objects.create(projet=self.projet, utilisateur=self.collegue, role=role(Role.Portee.PROJET, "rssi"))
        self.externe = ActeurProjet.objects.create(projet=self.projet, nom="Prestataire", email="presta@ext.test",
                                                   role=f.role_projet("developpeur"))
        self.api_rssi = APIClient()
        self.api_rssi.force_login(self.collegue)
        self.debut = (timezone.now() + timedelta(days=3)).replace(microsecond=0)

    def planifier(self, client=None, **extra):
        donnees = {"projet": str(self.projet.id), "titre": "Comité de pilotage", "debut": self.debut.isoformat(),
                   "fin": (self.debut + timedelta(hours=1)).isoformat(), "lieu": "Salle 2", "ordre_du_jour": "1. Avancement",
                   "participants": [str(self.chef.id), str(self.acteur_rssi.id), str(self.externe.id)], **extra}
        with self.captureOnCommitCallbacks(execute=True):
            return (client or self.api_a).post(URL, donnees, format="json")

    def invitations(self):
        return [m for m in mail.outbox if m.attachments]

    def test_invitations_une_par_destinataire(self):
        r = self.planifier()
        self.assertEqual(r.status_code, 201, r.content)
        envois = self.invitations()
        self.assertEqual(sorted(m.to[0] for m in envois), ["chef@a.test", "presta@ext.test", "rssi@a.test"])
        for m in envois:
            nom, contenu, type_mime = m.attachments[0]
            contenu = contenu.replace("\r\n ", "")  # lignes repliées (RFC 5545)
            self.assertEqual((nom, type_mime.split(";")[0]), ("invitation.ics", "text/calendar"))
            self.assertIn("METHOD:REQUEST", contenu)
            self.assertIn(f"UID:reunion-{r.data['id']}@solugation", contenu)
            self.assertIn(f"mailto:{m.to[0]}", contenu)
            autres = {"chef@a.test", "presta@ext.test", "rssi@a.test"} - {m.to[0]}
            self.assertFalse(any(a in contenu for a in autres))  # aucune autre adresse exposée
        mail.outbox.clear()
        self.planifier(inviter=False, titre="Point sans invitation")
        self.assertEqual(self.invitations(), [])

    def test_mise_a_jour_et_annulation(self):
        rid = self.planifier().data["id"]
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.api_a.patch(f"{URL}{rid}/", {"compte_rendu": "Brouillon"}, format="json")
        self.assertEqual(self.invitations(), [])  # le compte rendu ne change pas l'invitation
        with self.captureOnCommitCallbacks(execute=True):
            self.api_a.patch(f"{URL}{rid}/", {"lieu": "Visio"}, format="json")
        self.assertEqual(Reunion.objects.get(pk=rid).sequence, 1)
        self.assertIn("SEQUENCE:1", self.invitations()[0].attachments[0][1])
        mail.outbox.clear()
        membre = f.utilisateur(self.org_a, "membre@a.test")
        ActeurProjet.objects.create(projet=self.projet, utilisateur=membre, role=f.role_projet("developpeur"))
        client = APIClient()
        client.force_login(membre)
        self.assertEqual(client.post(f"{URL}{rid}/annuler/").status_code, 403)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.api_a.post(f"{URL}{rid}/annuler/").status_code, 200)
        self.assertIn("METHOD:CANCEL", self.invitations()[0].attachments[0][1])
        self.assertEqual(self.api_a.patch(f"{URL}{rid}/", {"lieu": "x"}, format="json").status_code, 400)

    def test_validations(self):
        r = self.planifier(fin=(self.debut - timedelta(hours=1)).isoformat())
        self.assertEqual(r.status_code, 400)
        autre = self.creer_projet(self.api_a, "Autre projet")
        acteur_autre = ActeurProjet.objects.filter(projet=autre).first()
        self.assertEqual(self.planifier(participants=[str(acteur_autre.id)]).status_code, 400)

    def test_isolation(self):
        rid = self.planifier().data["id"]
        self.assertEqual(self.api_b.get(f"{URL}{rid}/").status_code, 404)
        self.assertEqual(self.api_b.patch(f"{URL}{rid}/", {"titre": "x"}, format="json").status_code, 404)
        self.assertEqual(self.api_b.post(f"{URL}{rid}/annuler/").status_code, 404)
        self.assertEqual(self.api_b.post(f"{URL}{rid}/actions/", {"titre": "x"}, format="json").status_code, 404)
        self.assertEqual(self.api_b.get(URL).data["count"], 0)
        self.assertEqual(self.planifier(client=self.api_b).status_code, 400)

    def test_compte_rendu_fige_et_diffuse(self):
        rid = self.planifier().data["id"]
        url = f"{URL}{rid}/valider-compte-rendu/"
        self.assertEqual(self.api_a.post(url).status_code, 400)  # vide
        self.api_a.patch(f"{URL}{rid}/", {"compte_rendu": "Décision : lancer l'audit."}, format="json")
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.api_a.post(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["statut"], "tenue")
        self.assertIn("presta@ext.test", [m.to[0] for m in mail.outbox])  # externe compris
        self.assertEqual(self.api_a.patch(f"{URL}{rid}/", {"compte_rendu": "Après coup"}, format="json").status_code, 400)
        self.assertEqual(self.api_a.post(url).status_code, 409)

    def test_actions_deviennent_des_taches(self):
        rid = self.planifier().data["id"]
        r = self.api_a.post(f"{URL}{rid}/actions/", {"titre": "Planifier l'audit", "responsable": str(self.acteur_rssi.id),
                                                     "echeance": (timezone.localdate() + timedelta(days=15)).isoformat()}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        tache = Tache.objects.get(pk=r.data["id"])
        self.assertEqual((tache.origine, str(tache.reunion_id), tache.responsable), ("reunion", rid, self.acteur_rssi))
        self.assertEqual([t["titre"] for t in self.api_a.get(f"{URL}{rid}/actions/").data], ["Planifier l'audit"])
        self.assertEqual(self.api_a.get(f"{URL}{rid}/").data["nb_actions"], 1)
        autre = self.creer_projet(self.api_a, "Autre projet")
        intrus = ActeurProjet.objects.filter(projet=autre).first()
        self.assertEqual(self.api_a.post(f"{URL}{rid}/actions/", {"titre": "x", "responsable": str(intrus.id)}, format="json").status_code, 400)

    def test_rappel_calendrier_et_tableau_de_bord(self):
        rid = self.planifier(debut=(timezone.now() + timedelta(hours=12)).isoformat(),
                             fin=(timezone.now() + timedelta(hours=13)).isoformat()).data["id"]
        self.assertEqual(rappeler_reunions(), 1)
        self.assertEqual(rappeler_reunions(), 0)
        ics = self.api_a.get(f"/api/projets/{self.projet.id}/calendrier/").content.decode().replace("\r\n ", "")
        self.assertIn(f"UID:reunion-{rid}@solugation", ics)
        self.assertRegex(ics, r"DTSTART:\d{8}T\d{6}Z")
        elements = self.api_rssi.get(f"/api/projets/{self.projet.id}/tableau-de-bord/").data["pour_vous"]
        self.assertIn("Comité de pilotage", [e["titre"] for e in elements if e["type"] == "reunion"])
