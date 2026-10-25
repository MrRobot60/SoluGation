"""API : une organisation ne peut jamais lire, modifier ni lier les données d'une autre ;
dans une organisation, les droits suivent le rôle (admin, acteur, auditeur en lecture seule)."""

import hashlib
import io
import zipfile

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.audit.models import JournalAudit
from apps.comptes.models import Role
from apps.documents.models import DocumentDepose
from apps.projets.models import ActeurProjet, DocumentAttendu, Projet, ProjetReferentiel, StatutMesure
from apps.referentiels.models import Licence, Mesure, Referentiel

from . import fabriques as f

STOCKAGE_MEMOIRE = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def role(portee, code):
    return Role.objects.get(organisation=None, portee=portee, code=code)


def docx(macro=False):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document/>")
        if macro:
            z.writestr("word/vbaProject.bin", b"\x00" * 10)
    return tampon.getvalue()


@override_settings(STORAGES=STOCKAGE_MEMOIRE)
class BaseApi(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a, cls.org_b = f.organisation("Org A"), f.organisation("Org B")
        cls.admin_a = f.utilisateur(cls.org_a, "admin@a.test")
        cls.admin_a.role = role(Role.Portee.ORGANISATION, "admin")
        cls.admin_a.save()
        cls.user_a = f.utilisateur(cls.org_a, "chef@a.test")
        cls.user_b = f.utilisateur(cls.org_b, "chef@b.test")
        cls.rgs = f.referentiel("rgs")
        cls.mesure_rgs = Mesure.objects.create(referentiel=cls.rgs, identifiant="§2.1", intitule="Analyse des risques")
        cls.hygiene = f.referentiel("hygiene-anssi")
        Mesure.objects.create(referentiel=cls.hygiene, identifiant="M41", intitule="Analyse de risques formelle")
        cls.prive_a = Referentiel.objects.create(
            organisation=cls.org_a, code="iso27001", nom="ISO", version="2022", licence=Licence.PROPRIETAIRE
        )
        Mesure.objects.create(referentiel=cls.prive_a, identifiant="A.5.1", intitule="Politiques")

    def setUp(self):
        self.api_a, self.api_b = APIClient(), APIClient()
        self.api_a.force_login(self.user_a)
        self.api_b.force_login(self.user_b)

    def creer_projet(self, client, nom="Projet", referentiels=None, **extra):
        donnees = {"nom": nom, "type_bien": "application", "niveau_vise": "standard",
                   "referentiels": [str(r.id) for r in (referentiels or [self.rgs])], **extra}
        reponse = client.post("/api/projets/", donnees, format="json")
        self.assertEqual(reponse.status_code, 201, reponse.content)
        return Projet.objects.get(pk=reponse.data["id"])

    def deposer(self, client, projet, contenu=PDF, nom="preuve.pdf", **extra):
        fichier = io.BytesIO(contenu)
        fichier.name = nom
        return client.post("/api/documents-deposes/", {"projet": str(projet.id), "fichier": fichier, **extra},
                           format="multipart")


class IsolationApiTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet_a = self.creer_projet(self.api_a, "Projet A")
        self.projet_b = self.creer_projet(self.api_b, "Projet B")
        self.doc_a = DocumentAttendu.objects.create(projet=self.projet_a, intitule="PSSI")
        self.acteur_a = ActeurProjet.objects.get(projet=self.projet_a)

    def ids(self, reponse):
        donnees = reponse.data["results"] if isinstance(reponse.data, dict) and "results" in reponse.data else reponse.data
        return {str(o["id"]) for o in donnees}

    def test_listes_filtrees_par_organisation(self):
        for url in ("/api/projets/", "/api/acteurs/", "/api/documents-attendus/", "/api/documents-deposes/",
                    "/api/journal/", "/api/projet-referentiels/", "/api/statuts-mesures/", "/api/utilisateurs/"):
            with self.subTest(url=url):
                reponse = self.api_b.get(url)
                self.assertEqual(reponse.status_code, 200)
                self.assertFalse({str(self.projet_a.id), str(self.doc_a.id), str(self.acteur_a.id),
                                  str(self.user_a.id)} & self.ids(reponse))

    def test_filtre_projet_d_une_autre_organisation_vide(self):
        reponse = self.api_b.get(f"/api/documents-attendus/?projet={self.projet_a.id}")
        self.assertEqual(self.ids(reponse), set())

    def test_lecture_et_ecriture_directes_renvoient_404(self):
        for url in (f"/api/projets/{self.projet_a.id}/", f"/api/documents-attendus/{self.doc_a.id}/",
                    f"/api/acteurs/{self.acteur_a.id}/", f"/api/utilisateurs/{self.user_a.id}/"):
            with self.subTest(url=url):
                self.assertEqual(self.api_b.get(url).status_code, 404)
                self.assertIn(self.api_b.patch(url, {"nom": "x", "intitule": "x"}, format="json").status_code, (404, 405))
        self.assertEqual(self.api_b.delete(f"/api/documents-attendus/{self.doc_a.id}/").status_code, 404)
        self.assertTrue(DocumentAttendu.objects.filter(pk=self.doc_a.pk).exists())

    def test_creation_dans_le_projet_d_une_autre_organisation_refusee(self):
        reponse = self.api_b.post("/api/documents-attendus/", {"projet": str(self.projet_a.id), "intitule": "x"}, format="json")
        self.assertEqual(reponse.status_code, 400)
        self.assertFalse(DocumentAttendu.objects.filter(intitule="x").exists())

    def test_lien_vers_un_objet_d_une_autre_organisation_refuse(self):
        reponse = self.api_b.post("/api/documents-attendus/", {
            "projet": str(self.projet_b.id), "intitule": "x", "responsable": str(self.acteur_a.id)}, format="json")
        self.assertEqual(reponse.status_code, 400)
        reponse = self.api_b.post("/api/acteurs/", {
            "projet": str(self.projet_b.id), "utilisateur": str(self.user_a.id),
            "role": str(role(Role.Portee.PROJET, "rssi").id)}, format="json")
        self.assertEqual(reponse.status_code, 400)

    def test_referentiel_prive_invisible_et_inutilisable(self):
        self.assertNotIn(str(self.prive_a.id), self.ids(self.api_b.get("/api/referentiels/")))
        self.assertIn(str(self.prive_a.id), self.ids(self.api_a.get("/api/referentiels/")))
        self.assertEqual(self.api_b.get(f"/api/mesures/?referentiel={self.prive_a.id}").data["count"], 0)
        reponse = self.api_b.post("/api/projet-referentiels/", {
            "projet": str(self.projet_b.id), "referentiel": str(self.prive_a.id)}, format="json")
        self.assertEqual(reponse.status_code, 400)

    def test_documents_deposes_etanches(self):
        self.assertEqual(self.deposer(self.api_b, self.projet_a).status_code, 400)
        doc = DocumentDepose.objects.get(pk=self.deposer(self.api_a, self.projet_a).data["id"])
        self.assertEqual(self.api_b.get(f"/api/documents-deposes/{doc.id}/telecharger/").status_code, 404)
        self.assertEqual(self.api_b.get(f"/api/documents-deposes/{doc.id}/").status_code, 404)

    def test_journal_d_une_autre_organisation_invisible(self):
        self.assertTrue(JournalAudit.objects.filter(organisation=self.org_a).exists())
        reponse = self.api_b.get("/api/journal/")
        self.assertTrue(all(e["projet"] in (None, self.projet_b.id) for e in reponse.data["results"]))
        self.assertTrue(reponse.data["results"])

    def test_uuid_invalide_renvoie_400(self):
        self.assertEqual(self.api_b.get("/api/documents-attendus/?projet=pas-un-uuid").status_code, 400)


class DroitsApiTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet = self.creer_projet(self.api_a, "Projet A")

    def client_pour(self, utilisateur):
        client = APIClient()
        client.force_login(utilisateur)
        return client

    def test_anonyme_refuse(self):
        self.assertEqual(APIClient().get("/api/projets/").status_code, 403)

    def test_membre_non_acteur_ne_voit_pas_le_projet_mais_l_admin_si(self):
        autre = self.client_pour(f.utilisateur(self.org_a, "autre@a.test"))
        self.assertEqual(autre.get(f"/api/projets/{self.projet.id}/").status_code, 404)
        self.assertEqual(self.client_pour(self.admin_a).get(f"/api/projets/{self.projet.id}/").status_code, 200)

    def test_auditeur_organisation_en_lecture_seule(self):
        auditeur = f.utilisateur(self.org_a, "audit@a.test")
        auditeur.role = role(Role.Portee.ORGANISATION, "auditeur")
        auditeur.save()
        ActeurProjet.objects.create(projet=self.projet, utilisateur=auditeur, role=role(Role.Portee.PROJET, "rssi"))
        client = self.client_pour(auditeur)
        self.assertEqual(client.get(f"/api/projets/{self.projet.id}/").status_code, 200)
        self.assertEqual(client.patch(f"/api/projets/{self.projet.id}/", {"nom": "x"}, format="json").status_code, 403)
        self.assertEqual(client.post("/api/projets/", {}, format="json").status_code, 403)
        self.assertEqual(self.deposer(client, self.projet).status_code, 403)

    def test_acteur_auditeur_du_projet_en_lecture_seule(self):
        lecteur = f.utilisateur(self.org_a, "lecteur@a.test")
        ActeurProjet.objects.create(projet=self.projet, utilisateur=lecteur, role=role(Role.Portee.PROJET, "auditeur"))
        client = self.client_pour(lecteur)
        self.assertEqual(client.get(f"/api/projets/{self.projet.id}/").status_code, 200)
        self.assertEqual(client.patch(f"/api/projets/{self.projet.id}/", {"nom": "x"}, format="json").status_code, 403)
        reponse = client.post("/api/documents-attendus/", {"projet": str(self.projet.id), "intitule": "x"}, format="json")
        self.assertEqual(reponse.status_code, 403)

    def test_option_ia_reservee_a_l_admin(self):
        self.assertEqual(self.api_a.patch("/api/organisation/", {"ia_activee": False}, format="json").status_code, 403)
        reponse = self.client_pour(self.admin_a).patch("/api/organisation/", {"ia_activee": False}, format="json")
        self.assertEqual(reponse.status_code, 200)
        self.org_a.refresh_from_db()
        self.assertFalse(self.org_a.ia_activee)
        self.assertTrue(JournalAudit.objects.filter(objet_type="comptes.Organisation", action="modification").exists())

    def test_csrf_exige_hors_client_de_test(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user_a)
        self.assertEqual(client.post("/api/projets/", {}, format="json").status_code, 403)


class ProjetApiTests(BaseApi):
    def test_creation_createur_acteur_et_journal(self):
        projet = self.creer_projet(self.api_a, referentiels=[self.rgs, self.hygiene])
        self.assertEqual(projet.organisation, self.org_a)
        self.assertEqual(projet.referentiels.count(), 2)
        acteur = ActeurProjet.objects.get(projet=projet)
        self.assertEqual((acteur.utilisateur, acteur.role.code), (self.user_a, "chef-projet"))
        self.assertTrue(JournalAudit.objects.filter(projet=projet, action="creation").exists())

    def test_nombre_de_referentiels_borne(self):
        refs = [f.referentiel(c) for c in ("a", "b", "c")] + [self.rgs]
        for liste in ([], refs):
            reponse = self.api_a.post("/api/projets/", {"nom": "x", "type_bien": "si", "niveau_vise": "standard",
                                                        "referentiels": [str(r.id) for r in liste]}, format="json")
            self.assertEqual(reponse.status_code, 400)

    def test_pas_de_suppression_de_projet(self):
        projet = self.creer_projet(self.api_a)
        self.assertEqual(self.api_a.delete(f"/api/projets/{projet.id}/").status_code, 405)

    def test_modification_journalisee_avec_diff(self):
        projet = self.creer_projet(self.api_a)
        self.api_a.patch(f"/api/projets/{projet.id}/", {"statut": "en_cours"}, format="json")
        entree = JournalAudit.objects.filter(projet=projet, action="modification").latest("id")
        self.assertEqual(entree.donnees["statut"], {"avant": "brouillon", "apres": "en_cours"})

    def test_decision_non_modifiable_par_patch(self):
        projet = self.creer_projet(self.api_a)
        self.api_a.patch(f"/api/projets/{projet.id}/", {"decision": "homologation"}, format="json")
        projet.refresh_from_db()
        self.assertEqual(projet.decision, "")

    def test_statut_de_mesure_hors_referentiels_du_projet_refuse(self):
        projet = self.creer_projet(self.api_a)
        hors = Mesure.objects.get(referentiel=self.hygiene)
        reponse = self.api_a.post("/api/statuts-mesures/", {"projet": str(projet.id), "mesure": str(hors.id),
                                                            "statut": "conforme"}, format="json")
        self.assertEqual(reponse.status_code, 400)
        reponse = self.api_a.post("/api/statuts-mesures/", {"projet": str(projet.id), "mesure": str(self.mesure_rgs.id),
                                                            "statut": "conforme"}, format="json")
        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse.data["evalue_par"], self.user_a.id)


class ChecklistApiTests(BaseApi):
    def titres(self, projet):
        return set(DocumentAttendu.objects.filter(projet=projet).values_list("intitule", flat=True))

    def test_application_standard_sans_ebios(self):
        projet = self.creer_projet(self.api_a, referentiels=[self.rgs])
        reponse = self.api_a.post(f"/api/projets/{projet.id}/generer-checklist/")
        self.assertEqual(reponse.status_code, 201)
        titres = self.titres(projet)
        self.assertIn("Analyse de risques", titres)
        self.assertNotIn("Analyse de risques EBIOS RM (ateliers 1 à 5)", titres)
        self.assertIn("Rapport de test d'intrusion", titres)
        self.assertNotIn("Configuration de référence du poste de travail", titres)
        analyse = DocumentAttendu.objects.get(projet=projet, intitule="Analyse de risques")
        # Seules les mesures des référentiels du projet (RGS ici, pas l'hygiène).
        self.assertEqual(list(analyse.mesures.all()), [self.mesure_rgs])
        strategie = DocumentAttendu.objects.get(projet=projet, intitule="Stratégie d'homologation")
        self.assertEqual(strategie.responsable.utilisateur, self.user_a)
        self.assertIsNotNone(strategie.echeance)

    def test_idempotente(self):
        projet = self.creer_projet(self.api_a)
        nb = len(self.api_a.post(f"/api/projets/{projet.id}/generer-checklist/").data["documents"])
        reponse = self.api_a.post(f"/api/projets/{projet.id}/generer-checklist/")
        self.assertEqual((reponse.status_code, reponse.data["crees"], len(reponse.data["documents"])), (200, 0, nb))

    def test_poste_de_travail_elementaire_avec_ebios(self):
        projet = self.creer_projet(self.api_a, type_bien="poste_travail", niveau_vise="elementaire", ebios_active=True)
        self.api_a.post(f"/api/projets/{projet.id}/generer-checklist/")
        titres = self.titres(projet)
        self.assertIn("Configuration de référence du poste de travail", titres)
        self.assertIn("Analyse de risques EBIOS RM (ateliers 1 à 5)", titres)
        self.assertNotIn("Dossier d'architecture technique", titres)
        self.assertNotIn("Rapport d'audit de sécurité", titres)

    def test_reservee_aux_projets_accessibles(self):
        projet = self.creer_projet(self.api_a)
        self.assertEqual(self.api_b.post(f"/api/projets/{projet.id}/generer-checklist/").status_code, 404)


class UploadApiTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet = self.creer_projet(self.api_a)
        self.attendu = DocumentAttendu.objects.create(projet=self.projet, intitule="Analyse de risques")

    def test_depot_hash_nom_regenere_et_versions(self):
        r1 = self.deposer(self.api_a, self.projet, document_attendu=str(self.attendu.id))
        self.assertEqual(r1.status_code, 201, r1.content)
        doc = DocumentDepose.objects.get(pk=r1.data["id"])
        self.assertEqual(doc.sha256, hashlib.sha256(PDF).hexdigest())
        self.assertEqual((doc.version, doc.nom_original, doc.type_mime), (1, "preuve.pdf", "application/pdf"))
        self.assertTrue(doc.fichier.name.startswith(f"org/{self.org_a.id}/documentdepose/"))
        self.assertNotIn("preuve", doc.fichier.name)
        self.attendu.refresh_from_db()
        self.assertEqual(self.attendu.statut, DocumentAttendu.Statut.DEPOSE)
        r2 = self.deposer(self.api_a, self.projet, document_attendu=str(self.attendu.id))
        self.assertEqual(r2.data.get("version"), 2, r2.data)

    def test_types_refuses(self):
        cas = {
            "executable deguise": (b"MZ\x90\x00" + b"\x00" * 100, "rapport.pdf"),
            "html": (b"<!DOCTYPE html><script>alert(1)</script>", "notes.txt"),
            "svg": (b"<svg onload='alert(1)'></svg>", "image.txt"),
            "macro": (docx(macro=True), "doc.docx"),
            "vide": (b"", "vide.pdf"),
        }
        for nom, (contenu, fichier) in cas.items():
            with self.subTest(nom):
                self.assertEqual(self.deposer(self.api_a, self.projet, contenu, fichier).status_code, 400)
        self.assertFalse(DocumentDepose.objects.exists())

    def test_types_acceptes_et_extension_du_type_detecte(self):
        r = self.deposer(self.api_a, self.projet, docx(), "rapport.exe")
        self.assertEqual(r.status_code, 201, r.content)
        doc = DocumentDepose.objects.get(pk=r.data["id"])
        self.assertTrue(doc.fichier.name.endswith(".docx"))
        self.assertEqual(self.deposer(self.api_a, self.projet, b"<?xml version='1.0'?><NessusClientData_v2/>", "scan.nessus").status_code, 201)

    @override_settings(SOLUGATION_UPLOAD_MAX_OCTETS=1024)
    def test_taille_maximale(self):
        self.assertEqual(self.deposer(self.api_a, self.projet, PDF + b"0" * 2048).status_code, 400)

    def test_pas_de_modification_ni_suppression(self):
        doc_id = self.deposer(self.api_a, self.projet).data["id"]
        self.assertEqual(self.api_a.delete(f"/api/documents-deposes/{doc_id}/").status_code, 405)
        self.assertEqual(self.api_a.patch(f"/api/documents-deposes/{doc_id}/", {"commentaire": "x"}).status_code, 405)

    def test_telechargement_journalise(self):
        doc_id = self.deposer(self.api_a, self.projet).data["id"]
        reponse = self.api_a.get(f"/api/documents-deposes/{doc_id}/telecharger/")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(b"".join(reponse.streaming_content), PDF)
        self.assertIn('filename="preuve.pdf"', reponse["Content-Disposition"])
        self.assertTrue(JournalAudit.objects.filter(objet_id=str(doc_id), action="telechargement").exists())


class AuthApiTests(BaseApi):
    def test_connexion(self):
        client = APIClient()
        mauvais = client.post("/api/auth/connexion/", {"email": "chef@a.test", "password": "faux"}, format="json")
        inconnu = client.post("/api/auth/connexion/", {"email": "x@x.test", "password": "faux"}, format="json")
        self.assertEqual((mauvais.status_code, mauvais.data), (inconnu.status_code, inconnu.data))
        bon = client.post("/api/auth/connexion/", {"email": "chef@a.test", "password": "mot-de-passe-de-test-1"}, format="json")
        self.assertEqual(bon.status_code, 200)
        self.assertEqual(client.get("/api/auth/moi/").data["email"], "chef@a.test")
        self.assertTrue(JournalAudit.objects.filter(action="connexion", acteur=self.user_a).exists())

    def test_staff_sans_organisation_refuse(self):
        from apps.comptes.models import Utilisateur

        Utilisateur.objects.create_superuser(email="staff@x.test", password="mot-de-passe-de-test-1")
        reponse = APIClient().post("/api/auth/connexion/", {"email": "staff@x.test", "password": "mot-de-passe-de-test-1"}, format="json")
        self.assertEqual(reponse.status_code, 400)


class TableauDeBordApiTests(BaseApi):
    def setUp(self):
        super().setUp()
        from datetime import date, timedelta

        from apps.ai.models import AnalyseIA, ResultatAnalyseMesure
        from apps.projets.models import StatutMesure
        from apps.suivi.models import ActionPlan, Tache

        self.projet = self.creer_projet(self.api_a, referentiels=[self.rgs, self.hygiene])
        self.acteur = ActeurProjet.objects.get(projet=self.projet, utilisateur=self.user_a)
        StatutMesure.objects.create(projet=self.projet, mesure=self.mesure_rgs, statut="conforme")
        plan = ActionPlan.objects.create(projet=self.projet)
        hier = date.today() - timedelta(days=1)
        Tache.objects.create(projet=self.projet, plan=plan, titre="En retard", responsable=self.acteur, echeance=hier)
        Tache.objects.create(projet=self.projet, plan=plan, titre="Close", responsable=self.acteur,
                             statut=Tache.Statut.TERMINEE)
        autre = ActeurProjet.objects.create(projet=self.projet, nom="Externe", email="x@x.test",
                                            role=role(Role.Portee.PROJET, "rssi"))
        Tache.objects.create(projet=self.projet, plan=plan, titre="Pas pour moi", responsable=autre)
        DocumentAttendu.objects.create(projet=self.projet, intitule="PSSI", responsable=self.acteur,
                                       echeance=date.today() + timedelta(days=3))
        analyse = AnalyseIA.objects.create(projet=self.projet, type_analyse="analyse_documentaire", fournisseur="t",
                                           modele="t", version_prompt="1", demandee_par=self.user_a)
        ResultatAnalyseMesure.objects.create(projet=self.projet, analyse=analyse, mesure=self.mesure_rgs,
                                             couverture="partiel", justification="x")

    def test_agregats(self):
        r = self.api_a.get(f"/api/projets/{self.projet.id}/tableau-de-bord/")
        self.assertEqual(r.status_code, 200)
        d = r.data
        rgs = next(x for x in d["referentiels"] if x["code"] == "rgs")
        self.assertEqual(rgs["statuts"], {"conforme": 1, "partiel": 0, "manquant": 0, "non_applicable": 0, "non_evalue": 0})
        self.assertEqual(d["evaluation"], {"evaluees": 1, "total": 2})
        self.assertEqual(d["taches"], {"ouvertes": 2, "en_retard": 1})
        self.assertEqual(d["echeances"]["prochain_document"]["intitule"], "PSSI")
        self.assertEqual(d["a_valider"]["total"], 1)
        self.assertEqual(d["a_valider"]["conclusions"][0]["couverture"], "partiel")

    def test_pour_vous_ne_contient_que_mes_elements(self):
        d = self.api_a.get(f"/api/projets/{self.projet.id}/tableau-de-bord/").data
        titres = [e["titre"] for e in d["pour_vous"]]
        self.assertEqual(titres[0], "En retard")  # le retard passe en tête
        self.assertIn("PSSI", titres)
        self.assertNotIn("Pas pour moi", titres)
        self.assertNotIn("Close", titres)
        self.assertTrue(any(e["type"] == "validation_ia" for e in d["pour_vous"]))

    def test_isolation(self):
        self.assertEqual(self.api_b.get(f"/api/projets/{self.projet.id}/tableau-de-bord/").status_code, 404)


class AssistantCreationApiTests(BaseApi):
    def donnees(self, **extra):
        return {"nom": "Intranet", "type_bien": "si", "niveau_vise": "standard", "ebios_active": True,
                "referentiels": [str(self.rgs.id)], "generer_checklist": True, **extra}

    def test_projet_acteurs_et_checklist_en_une_requete(self):
        collegue = f.utilisateur(self.org_a, "rssi@a.test")
        r = self.api_a.post("/api/projets/", self.donnees(acteurs=[
            {"utilisateur": str(collegue.id), "role": str(role(Role.Portee.PROJET, "rssi").id)},
            {"nom": "Direction", "email": "dg@a.test", "role": str(role(Role.Portee.PROJET, "autorite-homologation").id)},
            {"utilisateur": str(self.user_a.id), "role": str(role(Role.Portee.PROJET, "chef-projet").id)},  # doublon ignoré
        ]), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        projet = Projet.objects.get(pk=r.data["id"])
        self.assertEqual(ActeurProjet.objects.filter(projet=projet).count(), 3)
        self.assertTrue(DocumentAttendu.objects.filter(projet=projet, intitule__startswith="Analyse de risques EBIOS").exists())
        strategie = DocumentAttendu.objects.get(projet=projet, intitule="Stratégie d'homologation")
        self.assertEqual(strategie.responsable.utilisateur, self.user_a)
        autorite = DocumentAttendu.objects.get(projet=projet, intitule="Décision d'homologation signée")
        self.assertEqual(autorite.responsable.email, "dg@a.test")
        entree = JournalAudit.objects.get(projet=projet, action="creation", objet_type="projets.Projet")
        self.assertEqual(entree.donnees["acteurs"], 3)
        self.assertNotIn("acteurs", r.data)  # champs d'écriture seule

    def test_acteur_d_une_autre_organisation_annule_tout(self):
        r = self.api_a.post("/api/projets/", self.donnees(acteurs=[
            {"utilisateur": str(self.user_b.id), "role": str(role(Role.Portee.PROJET, "rssi").id)}]), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Projet.objects.filter(nom="Intranet").exists())
        self.assertFalse(DocumentAttendu.objects.filter(projet__nom="Intranet").exists())

    def test_acteur_sans_compte_ni_email_refuse(self):
        r = self.api_a.post("/api/projets/", self.donnees(acteurs=[
            {"nom": "Quelqu'un", "role": str(role(Role.Portee.PROJET, "rssi").id)}]), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Projet.objects.filter(nom="Intranet").exists())

    def test_sans_checklist_par_defaut(self):
        donnees = self.donnees()
        del donnees["generer_checklist"]
        projet_id = self.api_a.post("/api/projets/", donnees, format="json").data["id"]
        self.assertFalse(DocumentAttendu.objects.filter(projet_id=projet_id).exists())


class EcranDocumentsApiTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet = self.creer_projet(self.api_a)
        self.chef = ActeurProjet.objects.get(projet=self.projet)
        self.attendu = DocumentAttendu.objects.create(projet=self.projet, intitule="PSSI", responsable=self.chef)
        self.attendu.mesures.add(self.mesure_rgs)
        # Décisions sur les pièces : user_a est aussi RSSI du projet.
        ActeurProjet.objects.create(projet=self.projet, utilisateur=self.user_a, role=role(Role.Portee.PROJET, "rssi"))

    def test_champs_lisibles(self):
        d = self.api_a.get(f"/api/documents-attendus/{self.attendu.id}/").data
        self.assertEqual(d["responsable_nom"], str(self.user_a))
        self.assertEqual(d["responsable_role"], "Chef de projet")
        self.assertEqual(d["mesures_couvertes"][0]["identifiant"], "§2.1")
        depot = self.deposer(self.api_a, self.projet, document_attendu=str(self.attendu.id)).data
        self.assertEqual(depot["depose_par_nom"], str(self.user_a))

    def test_validation_impossible_sans_version(self):
        r = self.api_a.patch(f"/api/documents-attendus/{self.attendu.id}/", {"statut": "valide"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_refus_puis_nouvelle_version_repasse_en_depose(self):
        self.deposer(self.api_a, self.projet, document_attendu=str(self.attendu.id))
        r = self.api_a.patch(f"/api/documents-attendus/{self.attendu.id}/", {"statut": "refuse"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.deposer(self.api_a, self.projet, document_attendu=str(self.attendu.id))
        self.attendu.refresh_from_db()
        self.assertEqual(self.attendu.statut, DocumentAttendu.Statut.DEPOSE)
        self.assertTrue(JournalAudit.objects.filter(objet_id=str(self.attendu.id), action="modification",
                                                    donnees__statut__apres="refuse").exists())



class DecisionsEtPreuvesApiTests(BaseApi):
    def setUp(self):
        super().setUp()
        from apps.ai.models import AnalyseIA, ResultatAnalyseMesure

        self.projet = self.creer_projet(self.api_a)  # user_a : chef de projet seulement
        self.attendu = DocumentAttendu.objects.create(projet=self.projet, intitule="PSSI")
        self.deposer(self.api_a, self.projet, document_attendu=str(self.attendu.id))
        self.rssi = f.utilisateur(self.org_a, "rssi@a.test")
        ActeurProjet.objects.create(projet=self.projet, utilisateur=self.rssi, role=role(Role.Portee.PROJET, "rssi"))
        self.api_rssi = APIClient()
        self.api_rssi.force_login(self.rssi)
        analyse = AnalyseIA.objects.create(projet=self.projet, type_analyse="analyse_documentaire", fournisseur="t",
                                           modele="t", version_prompt="1", demandee_par=self.user_a)
        self.resultat = ResultatAnalyseMesure.objects.create(projet=self.projet, analyse=analyse, mesure=self.mesure_rgs,
                                                             couverture="partiel", justification="Section incomplète.")

    def statut_piece(self, client, statut):
        return client.patch(f"/api/documents-attendus/{self.attendu.id}/", {"statut": statut}, format="json")

    def test_decision_sur_piece_reservee(self):
        self.assertEqual(self.statut_piece(self.api_a, "valide").status_code, 403)  # chef de projet
        self.assertEqual(self.statut_piece(self.api_rssi, "valide").status_code, 200)
        admin = APIClient()
        admin.force_login(self.admin_a)
        self.assertEqual(self.statut_piece(admin, "depose").status_code, 200)
        # Le chef de projet garde la main sur le reste (échéance, description).
        r = self.api_a.patch(f"/api/documents-attendus/{self.attendu.id}/", {"echeance": "2027-01-15"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_drapeau_peut_decider(self):
        self.assertFalse(self.api_a.get(f"/api/projets/{self.projet.id}/tableau-de-bord/").data["projet"]["peut_decider"])
        self.assertTrue(self.api_rssi.get(f"/api/projets/{self.projet.id}/tableau-de-bord/").data["projet"]["peut_decider"])

    def deposer_preuve(self, client, projet, mesures, **extra):
        fichier = io.BytesIO(PDF)
        fichier.name = "capture.pdf"
        return client.post("/api/preuves/", {"projet": str(projet.id), "titre": "Capture", "fichier": fichier,
                                             "mesures": [str(m.id) for m in mesures], **extra}, format="multipart")

    def test_preuves_versionnees(self):
        v1 = self.deposer_preuve(self.api_a, self.projet, [self.mesure_rgs])
        self.assertEqual((v1.status_code, v1.data["version"]), (201, 1), v1.content)
        v2 = self.deposer_preuve(self.api_a, self.projet, [self.mesure_rgs], serie=v1.data["serie"])
        self.assertEqual((v2.data["version"], v2.data["serie"]), (2, v1.data["serie"]))
        liste = self.api_a.get(f"/api/preuves/?mesure={self.mesure_rgs.id}").data["results"]
        self.assertEqual([p["version"] for p in liste], [2, 1])
        self.assertEqual(self.api_a.get(f"/api/preuves/{v2.data['id']}/telecharger/").status_code, 200)
        self.assertEqual(self.api_a.delete(f"/api/preuves/{v2.data['id']}/").status_code, 405)

    def test_preuve_mesure_hors_projet_refusee(self):
        hors = Mesure.objects.get(referentiel=self.hygiene)
        self.assertEqual(self.deposer_preuve(self.api_a, self.projet, [hors]).status_code, 400)

    def test_preuves_etanches(self):
        v1 = self.deposer_preuve(self.api_a, self.projet, [self.mesure_rgs]).data
        self.assertEqual(self.api_b.get(f"/api/preuves/{v1['id']}/").status_code, 404)
        self.assertEqual(self.api_b.get(f"/api/preuves/{v1['id']}/telecharger/").status_code, 404)
        projet_b = self.creer_projet(self.api_b, "Projet B")
        r = self.deposer_preuve(self.api_b, projet_b, [self.mesure_rgs], serie=v1["serie"])
        self.assertEqual(r.status_code, 400)  # une série d'une autre organisation n'existe pas

    def test_statuer_sur_conclusion_ia(self):
        url = f"/api/resultats-ia/{self.resultat.id}/statuer/"
        self.assertEqual(self.api_a.post(url, {"decision": "valide"}, format="json").status_code, 403)
        r = self.api_rssi.post(url, {"decision": "valide", "commentaire": "OK"}, format="json")
        self.assertEqual((r.status_code, r.data["statut_validation"]), (200, "valide"))
        statut = StatutMesure.objects.get(projet=self.projet, mesure=self.mesure_rgs)
        self.assertEqual((statut.statut, statut.resultat_analyse_id, statut.evalue_par), ("partiel", self.resultat.id, self.rssi))
        self.assertTrue(JournalAudit.objects.filter(action="validation_ia", objet_id=str(self.resultat.id)).exists())
        self.assertEqual(self.api_rssi.post(url, {"decision": "rejete"}, format="json").status_code, 409)
        # Reprise manuelle : le lien avec la proposition de l'IA est rompu.
        self.api_rssi.patch(f"/api/statuts-mesures/{statut.id}/", {"statut": "manquant", "justification": "Revu"}, format="json")
        statut.refresh_from_db()
        self.assertEqual((statut.statut, statut.resultat_analyse_id), ("manquant", None))

    def test_rejet_sans_effet_sur_le_statut(self):
        r = self.api_rssi.post(f"/api/resultats-ia/{self.resultat.id}/statuer/", {"decision": "rejete"}, format="json")
        self.assertEqual(r.data["statut_validation"], "rejete")
        self.assertFalse(StatutMesure.objects.filter(projet=self.projet, mesure=self.mesure_rgs).exists())
        self.assertEqual(self.api_b.get(f"/api/resultats-ia/{self.resultat.id}/").status_code, 404)
