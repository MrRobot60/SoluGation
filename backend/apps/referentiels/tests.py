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
