import unittest
import json
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from apps.core.tests import fabriques as f
from apps.referentiels.importeurs import ErreurImport
from apps.referentiels.importeurs.iso27001 import Iso27001
from apps.referentiels.importeurs.nist_csf import NistCsf
from apps.referentiels.importeurs.owasp_asvs import OwaspAsvs
from apps.referentiels.models import Referentiel

ASVS = {
    "Version": "5.0.0",
    "Requirements": [
        {"Shortcode": "V1", "Name": "Encoding", "Items": [
            {"Shortcode": "V1.1", "Name": "Architecture", "Items": [
                {"Shortcode": "V1.1.1", "Description": "Exigence niveau 2.", "L": "2"},
                {"Shortcode": "V1.1.2", "Description": "Exigence niveau 1.", "L": "1"},
            ]},
        ]},
    ],
}


def element(type_, ident, title="", text=""):
    return {"element_type": type_, "element_identifier": ident, "title": title, "text": text}


def projection(src, dest):
    return {"source_element_identifier": src, "dest_element_identifier": dest, "relationship_identifier": "projection"}


NIST = {"response": {"elements": {
    "elements": [
        element("function", "GV", "GOVERN"),
        element("category", "GV.OC", "Organizational Context"),
        element("subcategory", "GV.OC-02", text="Deuxième"),
        element("subcategory", "GV.OC-01", text="Première"),
        element("subcategory", "ID.BE-01", text="Retirée"),
        element("withdraw_reason", "WR-ID.BE-01", text="Incorporated into GV.OC-01"),
        element("sort", "S-GV.OC-01", "00001.00001.00001"),
        element("sort", "S-GV.OC-02", "00001.00001.00002"),
    ],
    "relationships": [projection("ID.BE-01", "WR-ID.BE-01")],
}}}


class BaseImport(TestCase):
    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp())
        (self.dossier / "private").mkdir()
        reglage = override_settings(SOLUGATION_DATA_DIR=self.dossier)
        reglage.enable()
        self.addCleanup(reglage.disable)

    def ecrire(self, nom, contenu):
        chemin = self.dossier / nom
        chemin.write_text(contenu if isinstance(contenu, str) else json.dumps(contenu), encoding="utf-8")
        return chemin


class ImportTests(BaseImport):
    def test_asvs_niveaux_cumulatifs_et_idempotence(self):
        chemin = self.ecrire("asvs.json", ASVS)
        r1 = OwaspAsvs(fichier=chemin).importer()
        r2 = OwaspAsvs(fichier=chemin).importer()
        self.assertEqual((r1.crees, r2.crees, r2.mis_a_jour), (2, 0, 0))
        mesure = r1.referentiel.mesures.get(identifiant="V1.1.1")
        self.assertEqual(mesure.niveaux, ["L2", "L3"])
        self.assertEqual(len(r1.referentiel.empreinte_source), 64)

    def test_nist_ignore_les_sous_categories_retirees_et_trie(self):
        ref = NistCsf(fichier=self.ecrire("csf.json", NIST)).importer().referentiel
        self.assertEqual(list(ref.mesures.values_list("identifiant", flat=True)), ["GV.OC-01", "GV.OC-02"])
        self.assertEqual(ref.mesures.first().categorie, "Govern › GV.OC Organizational Context")

    def test_nouvelle_version_signalee_sur_l_ancienne(self):
        ancienne = f.referentiel("owasp-asvs", version="4.0.3")
        nouvelle = OwaspAsvs(fichier=self.ecrire("asvs.json", ASVS)).importer().referentiel
        ancienne.refresh_from_db()
        self.assertEqual(ancienne.remplace_par, nouvelle)


class ImportIsoTests(BaseImport):
    def csv(self, avec_texte=True, dossier="private"):
        lignes = ["identifiant;intitule;categorie;texte"]
        lignes += [f"A.5.{i};Intitulé {i};Organisationnelles;{'Texte' if avec_texte else ''}" for i in range(1, 94)]
        return self.ecrire(f"{dossier}/iso.csv" if dossier else "iso.csv", "\n".join(lignes))

    def test_organisation_obligatoire(self):
        with self.assertRaises(ErreurImport):
            Iso27001(fichier=self.csv())

    def test_fichier_hors_data_private_refuse(self):
        org = f.organisation("Org ISO")
        with self.assertRaises(ErreurImport):
            Iso27001(fichier=self.csv(dossier=""), organisation=org).importer()

    def test_import_prive_a_l_organisation(self):
        org = f.organisation("Org ISO")
        ref = Iso27001(fichier=self.csv(), organisation=org).importer().referentiel
        self.assertEqual(ref.organisation, org)
        self.assertTrue(ref.texte_embarque)
        self.assertFalse(Referentiel.objects.filter(organisation__isnull=True, code="iso27001").exists())

    def test_sans_texte_bascule_texte_embarque(self):
        org = f.organisation("Org ISO")
        ref = Iso27001(fichier=self.csv(avec_texte=False), organisation=org).importer().referentiel
        self.assertFalse(ref.texte_embarque)
        self.assertIsNone(ref.mesures.first().texte_officiel)


II901_EXTRAIT = """Annexe 1 -Règles pour les entités situées hors du champ d'application de la PSSIE 9
Po litiqw:. organisation. goun:rnancc
Objecti[l :
Mettre en place une organisation adéquate,
garantissant la prise en compte de la sécurité.
Organisation SSI
ORG-SSI : organisation de la SSI. Une organisation dédiée est déployée.
Acteurs SSI
POT -AMOY : fourniture de supports amovibles. Des supports
sont fournis aux agents :
- la gestion des comptes ;
12
<<PAGE>>
Objecti[2:
Faire des personnes les maillons forts des SI.
DEY -FIL T -APPL : filtrage applicatif. Il est recommandé de filtrer.
Annexe 2 - Différentes classes de réseau
"""


class AnalyseIi901Tests(TestCase):
    def setUp(self):
        from apps.referentiels.importeurs.ii901 import Ii901

        self.importeur = Ii901()
        self.importeur.nb_objectifs, self.importeur.nb_regles = 2, 3

    def test_regles_objectifs_et_corrections_ocr(self):
        mesures = {m.identifiant: m for m in self.importeur.analyser(II901_EXTRAIT)}
        self.assertEqual(list(mesures), ["ORG-SSI", "PDT-AMOV", "DEV-FILT-APPL"])
        org = mesures["ORG-SSI"]
        self.assertEqual(org.intitule, "Organisation de la SSI")
        self.assertTrue(org.categorie.startswith("Objectif 1 — Mettre en place une organisation adéquate, garantissant"))
        self.assertNotIn("Acteurs SSI", org.texte)  # intertitre écarté
        self.assertIn("- la gestion des comptes;", mesures["PDT-AMOV"].texte)
        self.assertTrue(mesures["DEV-FILT-APPL"].categorie.startswith("Objectif 2 —"))

    def test_comptage_controle(self):
        self.importeur.nb_regles = 4
        with self.assertRaises(ErreurImport):
            self.importeur.analyser(II901_EXTRAIT)


class AnalyseRgsTests(TestCase):
    def test_regles_recommandations_et_identifiant_reutilise(self):
        from apps.referentiels.importeurs.rgs import Rgs

        lignes = [
            "2.1 Règles générales",
            "RègleImpact-1. L'impact de chaque clé doit",
            "être évalué.",
            "Justification :",
            "• texte de justification ignoré",
            "RecomControle-1. Il est recommandé de contrôler.",
            "RecomControle-1. Autre recommandation, même identifiant.",
        ]
        mesures = Rgs.analyser_annexe(lignes, "B2", "Annexe B2")
        self.assertEqual([m.identifiant for m in mesures], ["B2-RègleImpact-1", "B2-RecomControle-1", "B2-RecomControle-1-bis"])
        self.assertEqual(mesures[0].texte, "L'impact de chaque clé doit être évalué.")
        self.assertEqual(mesures[0].niveaux, ["obligatoire"])
        self.assertEqual(mesures[1].niveaux, ["recommandé"])
        self.assertEqual(mesures[0].categorie, "Annexe B2 › 2.1 Règles générales")


SOURCES = Path(__file__).resolve().parents[3] / "data" / "sources"


@unittest.skipUnless((SOURCES / "ii901").exists() and (SOURCES / "rgs").exists(), "PDF officiels absents (dépôt manuel)")
class SourcesReellesTests(TestCase):
    """Vérifie les parseurs sur les vrais PDF quand ils sont déposés dans data/sources/."""

    def test_ii901(self):
        from apps.referentiels.importeurs.ii901 import Ii901

        mesures = Ii901(fichier=SOURCES / "ii901/2015/cir_39217.pdf").lire(SOURCES / "ii901/2015/cir_39217.pdf")
        self.assertEqual(len(mesures), 178)

    def test_rgs(self):
        from apps.referentiels.importeurs.rgs import Rgs

        self.assertEqual(len(Rgs().lire(SOURCES / "rgs/2.0")), 155)
