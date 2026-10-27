"""Rapports de scan : lecture Nessus, OpenVAS et CSV ; XML hostiles refusés ; isolation ; constats comparés au
scan précédent (faux positifs conservés) ; tâches créées sur demande, une par vulnérabilité, sans doublon."""

import io

from rest_framework.test import APIClient

from apps.comptes.models import Role
from apps.core.tests import fabriques as f
from apps.core.tests.test_api import BaseApi, role
from apps.projets.models import ActeurProjet
from apps.suivi.models import Tache

from .analyseurs import lire_rapport
from .models import ConstatScan, ImportScan

NESSUS = b"""<?xml version="1.0" ?>
<NessusClientData_v2><Report name="Scan interne">
<ReportHost name="srv-web"><HostProperties><tag name="host-ip">10.0.0.10</tag><tag name="HOST_START">Mon Oct 26 09:00:00 2026</tag></HostProperties>
<ReportItem port="443" protocol="tcp" severity="3" pluginID="156860" pluginName="Apache 2.4.x &lt; 2.4.58 Multiple Vulnerabilities">
<synopsis>Le serveur web est vuln&#233;rable.</synopsis><description>Version obsol&#232;te.</description>
<solution>Mettre &#224; jour Apache en 2.4.58 ou ult&#233;rieur.</solution><cvss3_base_score>8.1</cvss3_base_score>
<cve>CVE-2023-45802</cve><cve>CVE-2023-43622</cve></ReportItem>
<ReportItem port="0" protocol="tcp" severity="0" pluginID="19506" pluginName="Nessus Scan Information"><description>Info</description></ReportItem>
</ReportHost>
<ReportHost name="srv-app"><HostProperties><tag name="host-ip">10.0.0.11</tag></HostProperties>
<ReportItem port="443" protocol="tcp" severity="3" pluginID="156860" pluginName="Apache 2.4.x &lt; 2.4.58 Multiple Vulnerabilities">
<cvss3_base_score>8.1</cvss3_base_score><cve>CVE-2023-45802</cve></ReportItem>
<ReportItem port="22" protocol="tcp" severity="2" pluginID="90317" pluginName="SSH Weak Algorithms Supported"><cvss_base_score>4.3</cvss_base_score></ReportItem>
</ReportHost></Report></NessusClientData_v2>"""

OPENVAS = b"""<?xml version="1.0" encoding="UTF-8"?>
<report id="r1"><creation_time>2026-10-26T09:00:00Z</creation_time><report id="r1"><results>
<result id="a"><name>OpenSSL multiples vuln&#233;rabilit&#233;s</name><host>10.0.0.20</host><port>443/tcp</port>
<nvt oid="1.3.6.1.4.1.25623.1.0.1"><name>OpenSSL</name><tags>summary=OpenSSL obsol&#232;te|solution=Mettre &#224; jour OpenSSL</tags>
<refs><ref type="cve" id="CVE-2024-0727"/></refs></nvt><threat>High</threat><severity>9.8</severity><description>D&#233;tail</description></result>
<result id="b"><name>TLS 1.0 activ&#233;</name><host>10.0.0.20</host><port>443/tcp</port>
<nvt oid="1.3.6.1.4.1.25623.1.0.2"><name>TLS</name></nvt><threat>Medium</threat><severity>5.0</severity></result>
</results></report></report>"""

CSV = "Actif;CVE;Score CVSS;Criticité;Titre;Solution\nposte-01;CVE-2024-21412;8.1;Élevée;Contournement SmartScreen;Appliquer KB5034763\n".encode()

MILLIARD_DE_RIRES = b"""<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>
<NessusClientData_v2>&b;</NessusClientData_v2>"""
XXE = b"""<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><NessusClientData_v2>&x;</NessusClientData_v2>"""


class AnalyseursTests(BaseApi):
    def test_nessus(self):
        r = lire_rapport(NESSUS, "application/xml")
        self.assertEqual(r.outil, "nessus")
        apache = [c for c in r.constats if c.identifiant_outil == "nessus:156860"]
        self.assertEqual({c.hote for c in apache}, {"10.0.0.10", "10.0.0.11"})
        self.assertEqual((apache[0].severite, str(apache[0].cvss), apache[0].port), ("haute", "8.1", 443))
        self.assertEqual(apache[0].cve, ["CVE-2023-43622", "CVE-2023-45802"])
        self.assertIn("2.4.58", apache[0].solution)
        self.assertEqual(r.date_scan.year, 2026)

    def test_openvas(self):
        r = lire_rapport(OPENVAS, "application/xml")
        self.assertEqual(r.outil, "openvas")
        ssl = r.constats[0]
        self.assertEqual((ssl.severite, ssl.hote, ssl.port, ssl.protocole, ssl.cve), ("critique", "10.0.0.20", 443, "tcp", ["CVE-2024-0727"]))
        self.assertEqual(ssl.solution, "Mettre à jour OpenSSL")
        self.assertEqual(r.constats[1].severite, "moyenne")

    def test_csv(self):
        r = lire_rapport(CSV, "text/csv")
        c = r.constats[0]
        self.assertEqual((c.hote, c.severite, c.cve, c.titre), ("poste-01", "haute", ["CVE-2024-21412"], "Contournement SmartScreen"))


class ImportTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.projet = self.creer_projet(self.api_a, "Projet A")
        rssi = f.utilisateur(self.org_a, "rssi@a.test")
        ActeurProjet.objects.create(projet=self.projet, utilisateur=rssi, role=role(Role.Portee.PROJET, "rssi"))
        self.api_rssi = APIClient()
        self.api_rssi.force_login(rssi)

    def importer(self, contenu, nom="scan.nessus", client=None, projet=None):
        fichier = io.BytesIO(contenu)
        fichier.name = nom
        return (client or self.api_a).post("/api/imports-scans/", {"projet": str((projet or self.projet).id), "fichier": fichier}, format="multipart")

    def test_import_et_bilan(self):
        r = self.importer(NESSUS)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data["outil"], r.data["etat"]), ("nessus", "traite"))
        self.assertEqual(r.data["bilan"]["total"], 4)
        self.assertEqual(r.data["bilan"]["par_severite"]["haute"], 2)
        self.assertEqual(len(r.data["sha256"]), 64)
        imp = ImportScan.objects.get(pk=r.data["id"])
        self.assertRegex(imp.fichier.name, rf"^org/{self.org_a.id}/importscan/[0-9a-f]{{32}}\.xml$")  # nom régénéré, isolé

    def test_xml_hostiles_refuses(self):
        for contenu in (MILLIARD_DE_RIRES, XXE):
            with self.subTest(contenu=contenu[:40]):
                r = self.importer(contenu)
                self.assertEqual(r.status_code, 400)
                self.assertIn("refusé", r.data["detail"])
        self.assertFalse(ConstatScan.objects.exists())
        self.assertEqual(self.importer(b"<?xml version='1.0'?><autre/>", nom="x.xml").status_code, 400)
        self.assertEqual(self.importer(b"%PDF-1.4\n%%EOF", nom="x.pdf").status_code, 400)  # pas un rapport de scan

    def test_isolation(self):
        imp = self.importer(NESSUS).data["id"]
        constat = ConstatScan.objects.filter(import_scan_id=imp).first()
        self.assertEqual(self.api_b.get(f"/api/imports-scans/{imp}/").status_code, 404)
        self.assertEqual(self.api_b.get(f"/api/imports-scans/{imp}/telecharger/").status_code, 404)
        self.assertEqual(self.api_b.get("/api/constats-scans/").data["count"], 0)
        self.assertEqual(self.api_b.post(f"/api/constats-scans/{constat.id}/statuer/", {"statut": "traite"}, format="json").status_code, 404)
        self.assertEqual(self.api_b.post(f"/api/imports-scans/{imp}/creer-taches/", {"severite_min": "faible"}, format="json").status_code, 404)
        self.assertEqual(self.importer(NESSUS, client=self.api_b).status_code, 400)  # projet d'une autre organisation

    def test_taches_par_vulnerabilite_sans_doublon(self):
        imp = self.importer(NESSUS).data["id"]
        self.assertFalse(Tache.objects.filter(projet=self.projet).exists())  # rien sans demande explicite
        r = self.api_a.post(f"/api/imports-scans/{imp}/creer-taches/", {"severite_min": "moyenne"}, format="json")
        self.assertEqual(r.data["crees"], 2)  # Apache (2 hôtes, une seule tâche) + SSH ; l'information est ignorée
        apache = Tache.objects.get(projet=self.projet, titre__startswith="Corriger : Apache")
        self.assertEqual((apache.origine, apache.priorite), ("scan", "haute"))
        self.assertIn("10.0.0.10:443", apache.description)
        self.assertIn("CVE-2023-45802", apache.description)
        # Nouveau scan : la vulnérabilité déjà suivie ne crée pas de seconde tâche.
        imp2 = self.importer(NESSUS).data["id"]
        self.assertEqual(self.api_a.post(f"/api/imports-scans/{imp2}/creer-taches/", {"severite_min": "faible"}, format="json").data["crees"], 0)

    def test_faux_positif_conserve_et_acceptation_reservee(self):
        imp = self.importer(NESSUS).data["id"]
        ssh = ConstatScan.objects.get(import_scan_id=imp, identifiant_outil="nessus:90317")
        url = f"/api/constats-scans/{ssh.id}/statuer/"
        self.assertEqual(self.api_a.post(url, {"statut": "faux_positif"}, format="json").status_code, 400)  # non justifié
        self.assertEqual(self.api_a.post(url, {"statut": "accepte", "commentaire": "x"}, format="json").status_code, 403)
        self.assertEqual(self.api_a.post(url, {"statut": "faux_positif", "commentaire": "Algorithmes désactivés"}, format="json").status_code, 200)
        r = self.importer(NESSUS)
        self.assertEqual((r.data["bilan"]["deja_vus"], r.data["bilan"]["nouveaux"]), (4, 0))
        nouveau = ConstatScan.objects.get(import_scan_id=r.data["id"], identifiant_outil="nessus:90317")
        self.assertEqual((nouveau.statut, nouveau.commentaire_statut), ("faux_positif", "Algorithmes désactivés"))
        apache = ConstatScan.objects.filter(import_scan_id=r.data["id"], identifiant_outil="nessus:156860").first()
        r = self.api_rssi.post(f"/api/constats-scans/{apache.id}/statuer/", {"statut": "accepte", "commentaire": "Serveurs isolés",
                                                                             "tous_les_hotes": True}, format="json")
        self.assertEqual(r.data["modifies"], 2)

    def test_auditeur_ne_depose_pas(self):
        lecteur = f.utilisateur(self.org_a, "lecteur@a.test")
        ActeurProjet.objects.create(projet=self.projet, utilisateur=lecteur, role=role(Role.Portee.PROJET, "auditeur"))
        client = APIClient()
        client.force_login(lecteur)
        self.assertEqual(self.importer(NESSUS, client=client).status_code, 403)
