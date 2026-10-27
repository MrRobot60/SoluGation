"""Import des rapports de scan : constats normalisés, comparaison avec le scan précédent du même outil, et
création des tâches (une par vulnérabilité, tous hôtes confondus), sur décision humaine uniquement."""

from datetime import date, timedelta

from django.db import transaction

from apps.suivi.models import Tache
from apps.suivi.services import TACHES_CLOSES, plan_du_projet, responsable_par_defaut

from .analyseurs import SEVERITES, lire_rapport
from .models import ConstatScan, ImportScan

PRIORITE = {"critique": Tache.Priorite.CRITIQUE, "haute": Tache.Priorite.HAUTE, "moyenne": Tache.Priorite.MOYENNE, "faible": Tache.Priorite.BASSE}
DELAI = {"critique": 15, "haute": 30, "moyenne": 60, "faible": 90}
STATUTS_HERITES = (ConstatScan.Statut.FAUX_POSITIF, ConstatScan.Statut.ACCEPTE)
HOTES_MAX = 30


def _cle(c):
    return (c.identifiant_outil, c.hote, c.port, c.protocole or "")


@transaction.atomic
def traiter(import_scan):
    """Lit le fichier déposé, crée les constats et calcule le bilan. Un faux positif ou un risque accepté
    lors d'un scan précédent le reste (même vulnérabilité, même hôte, même port)."""
    with import_scan.fichier.open("rb") as f:
        rapport = lire_rapport(f.read(), import_scan.type_mime)
    projet = import_scan.projet
    precedent = (ImportScan.objects.filter(projet=projet, outil=rapport.outil, etat=ImportScan.Etat.TRAITE)
                 .exclude(pk=import_scan.pk).order_by("-depose_le").first())
    anciens = {c.cle: c for c in precedent.constats.all()} if precedent else {}
    vus = set()
    for c in rapport.constats:
        cle = _cle(c)
        if cle in vus:  # doublon dans le même rapport
            continue
        vus.add(cle)
        ancien = anciens.get(cle)
        herite = ancien if ancien and ancien.statut in STATUTS_HERITES else None
        ConstatScan.objects.create(
            projet=projet, import_scan=import_scan, identifiant_outil=c.identifiant_outil[:100], titre=c.titre, severite=c.severite,
            cvss=c.cvss, cve=c.cve, hote=c.hote, port=c.port, protocole=c.protocole, description=c.description, solution=c.solution,
            statut=herite.statut if herite else ConstatScan.Statut.OUVERT,
            commentaire_statut=herite.commentaire_statut if herite else "", statut_par=herite.statut_par if herite else None,
            statut_le=herite.statut_le if herite else None,
        )
    import_scan.outil, import_scan.date_scan, import_scan.etat = rapport.outil, rapport.date_scan, ImportScan.Etat.TRAITE
    import_scan.bilan = {
        "total": len(vus), "par_severite": {s: sum(1 for c in rapport.constats if _cle(c) in vus and c.severite == s) for s in SEVERITES},
        "nouveaux": len(vus - set(anciens)), "deja_vus": len(vus & set(anciens)), "disparus": len(set(anciens) - vus),
        "precedent": str(precedent.pk) if precedent else None,
    }
    import_scan.save(update_fields=["outil", "date_scan", "etat", "bilan"])
    return import_scan


def groupes(import_scan, identifiants=None, severite_min=None):
    """Constats ouverts regroupés par vulnérabilité (identifiant de l'outil)."""
    qs = import_scan.constats.filter(statut=ConstatScan.Statut.OUVERT).order_by("-cvss", "hote")
    if identifiants is not None:
        qs = qs.filter(identifiant_outil__in=identifiants)
    if severite_min:
        qs = qs.filter(severite__in=SEVERITES[SEVERITES.index(severite_min):])
    resultat = {}
    for c in qs:
        resultat.setdefault(c.identifiant_outil, []).append(c)
    return resultat


def creer_taches(import_scan, identifiants=None, severite_min=None, aujourd_hui=None):
    """Une tâche par vulnérabilité ouverte qui n'a pas déjà de tâche ouverte dans le projet. Renvoie les tâches créées."""
    projet, aujourd_hui = import_scan.projet, aujourd_hui or date.today()
    deja = set(Tache.objects.filter(projet=projet, constat_scan__isnull=False).exclude(statut__in=TACHES_CLOSES)
               .values_list("constat_scan__identifiant_outil", flat=True))
    crees = []
    for identifiant, constats in groupes(import_scan, identifiants, severite_min).items():
        if identifiant in deja or constats[0].severite == "info":
            continue
        tete = max(constats, key=lambda c: (SEVERITES.index(c.severite), c.cvss or 0))
        hotes = sorted({f"{c.hote}{f':{c.port}' if c.port else ''}" for c in constats if c.hote})
        cves = sorted({v for c in constats for v in c.cve})
        lignes = [tete.description[:1500], f"Concerne {len(hotes)} hôte(s) : {', '.join(hotes[:HOTES_MAX])}{'…' if len(hotes) > HOTES_MAX else ''}."]
        if cves:
            lignes.append(f"CVE : {', '.join(cves[:20])}{'…' if len(cves) > 20 else ''}.")
        if tete.solution:
            lignes.append(f"Solution proposée par l'outil : {tete.solution[:1500]}")
        crees.append(Tache.objects.create(
            projet=projet, plan=plan_du_projet(projet), titre=f"Corriger : {tete.titre}"[:300], origine=Tache.Origine.SCAN,
            description="\n\n".join(l for l in lignes if l), constat_scan=tete, priorite=PRIORITE[tete.severite],
            responsable=responsable_par_defaut(projet), echeance=aujourd_hui + timedelta(days=DELAI[tete.severite]),
            preuve_attendue="Nouveau scan sans ce constat, ou preuve du correctif appliqué (version, configuration).",
        ))
    return crees
