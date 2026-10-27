"""Lecture des rapports de scan de vulnérabilités, normalisés en constats.

- Nessus : fichier `.nessus` (XML NessusClientData_v2) ;
- OpenVAS / Greenbone : rapport XML (élément <report> et ses <result>) ;
- Cyberwatch, et tout export CSV : en-têtes reconnus en français ou en anglais (actif, CVE, CVSS, sévérité…).
  Format à valider sur un export réel : seules les colonnes reconnues sont reprises.

Les XML sont lus avec defusedxml (pas d'entités externes ni d'expansion : XXE et « milliard de rires » refusés)."""

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

SEVERITES = ["info", "faible", "moyenne", "haute", "critique"]
CVE = re.compile(r"CVE-\d{4}-\d{4,}", re.I)
TEXTE_MAX = 8000


class RapportIllisible(Exception):
    pass


@dataclass
class Constat:
    identifiant_outil: str
    titre: str
    severite: str
    cvss: Decimal | None = None
    cve: list = field(default_factory=list)
    hote: str = ""
    port: int | None = None
    protocole: str = ""
    description: str = ""
    solution: str = ""


@dataclass
class Rapport:
    outil: str
    constats: list
    date_scan: datetime | None = None


def severite_depuis_score(score):
    if score is None:
        return "info"
    return "critique" if score >= 9 else "haute" if score >= 7 else "moyenne" if score >= 4 else "faible" if score > 0 else "info"


def _decimal(valeur):
    try:
        d = Decimal(str(valeur).strip().replace(",", "."))
        return d if Decimal(0) <= d <= Decimal(10) else None
    except (InvalidOperation, ValueError):
        return None


def _entier(valeur):
    try:
        n = int(str(valeur).strip())
        return n if 0 < n < 65536 else None
    except (TypeError, ValueError):
        return None


def _texte(noeud, chemin):
    trouve = noeud.find(chemin) if noeud is not None else None
    return (trouve.text or "").strip()[:TEXTE_MAX] if trouve is not None else ""


def _cves(*textes):
    return sorted({c.upper() for t in textes if t for c in CVE.findall(t)})


def nessus(racine):
    constats, debut = [], None
    for hote in racine.iter("ReportHost"):
        nom = hote.get("name", "")
        proprietes = {t.get("name"): (t.text or "") for t in hote.iter("tag")}
        nom = proprietes.get("host-ip") or nom
        if not debut and proprietes.get("HOST_START"):
            try:
                debut = datetime.strptime(proprietes["HOST_START"], "%a %b %d %H:%M:%S %Y")
            except ValueError:
                pass
        for item in hote.iter("ReportItem"):
            niveau = _entier(item.get("severity")) or 0
            cvss = _decimal(_texte(item, "cvss3_base_score") or _texte(item, "cvss_base_score"))
            constats.append(Constat(
                identifiant_outil=f"nessus:{item.get('pluginID', '')}", titre=(item.get("pluginName") or _texte(item, "plugin_name"))[:500],
                severite=SEVERITES[min(max(niveau, 0), 4)], cvss=cvss, cve=_cves(*[(c.text or "") for c in item.iter("cve")]),
                hote=nom[:255], port=_entier(item.get("port")), protocole=(item.get("protocol") or "")[:10],
                description=(_texte(item, "synopsis") + "\n\n" + _texte(item, "description")).strip()[:TEXTE_MAX],
                solution=_texte(item, "solution"),
            ))
    return Rapport("nessus", constats, debut)


def openvas(racine):
    constats = []
    rapport = racine if racine.tag == "report" else next(racine.iter("report"), racine)
    for r in rapport.iter("result"):
        if r.find("nvt") is None:  # <result> imbriqué dans d'autres éléments (deltas, notes) : ignoré
            continue
        nvt = r.find("nvt")
        score = _decimal(_texte(r, "severity") or _texte(nvt, "cvss_base"))
        menace = _texte(r, "threat").lower()
        severite = {"log": "info", "low": "faible", "medium": "moyenne", "high": "haute", "critical": "critique"}.get(menace) \
            or severite_depuis_score(score)
        if severite == "haute" and score is not None and score >= 9:
            severite = "critique"  # OpenVAS classe « High » jusqu'à 10
        tags = dict(p.split("=", 1) for p in _texte(nvt, "tags").split("|") if "=" in p)
        port, protocole = (_texte(r, "port").split("/", 1) + [""])[:2]
        refs = [ref.get("id", "") for ref in nvt.iter("ref") if ref.get("type", "").lower() == "cve"]
        constats.append(Constat(
            identifiant_outil=f"openvas:{nvt.get('oid', '')}", titre=(_texte(r, "name") or _texte(nvt, "name"))[:500], severite=severite,
            cvss=score, cve=_cves(" ".join(refs), _texte(nvt, "cve")), hote=_texte(r, "host")[:255], port=_entier(port),
            protocole=protocole[:10], description=(tags.get("summary", "") + "\n\n" + _texte(r, "description")).strip()[:TEXTE_MAX],
            solution=(_texte(nvt, "solution") or tags.get("solution", ""))[:TEXTE_MAX],
        ))
    date = None
    if texte := _texte(rapport, "scan_start") or _texte(racine, "creation_time"):
        try:
            date = datetime.fromisoformat(texte.replace("Z", "+00:00"))
        except ValueError:
            pass
    return Rapport("openvas", constats, date)


COLONNES = {  # synonymes d'en-têtes (minuscules, sans accents ni espaces superflus)
    "hote": ("asset", "actif", "hostname", "host", "machine", "serveur", "ip", "adresse ip", "nom"),
    "cve": ("cve", "cve code", "code cve", "cves", "identifiant cve"),
    "cvss": ("cvss", "cvss v3", "cvss3", "score cvss", "cvss score", "score"),
    "severite": ("severity", "severite", "criticite", "niveau", "level", "priority", "priorite"),
    "titre": ("title", "titre", "name", "vulnerabilite", "vulnerability", "intitule", "description courte"),
    "description": ("description", "details", "detail", "resume", "summary"),
    "solution": ("solution", "remediation", "correctif", "fix", "recommandation"),
    "port": ("port",),
    "identifiant": ("id", "identifiant", "plugin id", "reference"),
}
NIVEAUX_TEXTE = {"critical": "critique", "critique": "critique", "high": "haute", "haute": "haute", "eleve": "haute", "elevee": "haute",
                 "medium": "moyenne", "moyenne": "moyenne", "moyen": "moyenne", "low": "faible", "faible": "faible", "basse": "faible",
                 "info": "info", "information": "info", "none": "info"}


def _norme(texte):
    texte = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[\s_\-]+", " ", texte).strip()


def tableur(contenu):
    texte = contenu.decode("utf-8-sig", errors="replace")
    try:
        dialecte = csv.Sniffer().sniff(texte[:4096], delimiters=",;\t")
    except csv.Error:
        dialecte = csv.excel
    lignes = csv.DictReader(io.StringIO(texte), dialect=dialecte)
    if not lignes.fieldnames:
        raise RapportIllisible("CSV sans en-tête.")
    entetes = {_norme(h): h for h in lignes.fieldnames}
    correspondance = {cle: next((entetes[s] for s in synonymes if s in entetes), None) for cle, synonymes in COLONNES.items()}
    if not (correspondance["cve"] or correspondance["titre"]):
        raise RapportIllisible("Colonnes non reconnues : il faut au moins une colonne CVE ou titre.")
    constats = []
    for ligne in lignes:
        def lire(cle, ligne=ligne):
            return (ligne.get(correspondance[cle]) or "").strip() if correspondance[cle] else ""

        cves = _cves(lire("cve"))
        titre = lire("titre") or (", ".join(cves) if cves else "")
        if not titre:
            continue
        cvss = _decimal(lire("cvss")) if lire("cvss") else None
        severite = NIVEAUX_TEXTE.get(_norme(lire("severite"))) or severite_depuis_score(cvss)
        identifiant = lire("identifiant") or (cves[0] if cves else titre[:90])
        constats.append(Constat(identifiant_outil=f"csv:{identifiant}"[:100], titre=titre[:500], severite=severite, cvss=cvss, cve=cves,
                                hote=lire("hote")[:255], port=_entier(lire("port")), description=lire("description")[:TEXTE_MAX],
                                solution=lire("solution")[:TEXTE_MAX]))
    return Rapport("cyberwatch", constats)


def lire_rapport(contenu, type_mime):
    """Détecte l'outil d'après le contenu (et non l'extension) et renvoie le rapport normalisé."""
    if type_mime == "text/csv":
        return tableur(contenu)
    try:
        racine = ElementTree.fromstring(contenu)
    except DefusedXmlException:
        raise RapportIllisible("XML refusé : entités ou références externes interdites.") from None
    except ElementTree.ParseError:
        raise RapportIllisible("XML mal formé.") from None
    if racine.tag in ("NessusClientData_v2", "NessusClientData"):
        return nessus(racine)
    if racine.tag in ("report", "get_reports_response", "envelope") or racine.find(".//report/results") is not None:
        return openvas(racine)
    raise RapportIllisible("Format non reconnu : rapport Nessus (.nessus), OpenVAS (XML) ou CSV attendu.")
