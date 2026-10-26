"""Instantané des données structurées d'un projet, figé dans le rapport (JSON) : il sert à rédiger le texte,
à produire le PDF sans requête ni appel IA, et à comparer deux versions du rapport."""

from datetime import date

from django.db.models import Count
from django.utils import timezone

from apps.ai.models import AnalyseIA, RecommandationIA, ResultatAnalyseMesure
from apps.core.models import StatutValidation
from apps.projets.api import nom_acteur
from apps.projets.models import ActeurProjet, DocumentAttendu, StatutMesure
from apps.projets.tableau_de_bord import STATUTS, _referentiels
from apps.risques.models import Derogation, RisqueResiduel
from apps.suivi.models import Tache
from apps.suivi.services import TACHES_CLOSES

MANQUEMENTS_MAX = 80
TACHES_MAX = 80
ORDRE_PRIORITE = {"critique": 0, "haute": 1, "moyenne": 2, "basse": 3}


def _pct(n, total):
    return round(100 * n / total) if total else 0


def instantane(projet, aujourd_hui=None):
    aujourd_hui = aujourd_hui or date.today()
    referentiels = []
    for r in _referentiels(projet):
        s = r["statuts"]
        applicables = r["total"] - s["non_applicable"]
        referentiels.append({
            "code": r["code"], "nom": r["nom"], "version": r["version"], "total": r["total"], "statuts": s,
            "evaluees": r["total"] - s["non_evalue"], "taux_evaluation": _pct(r["total"] - s["non_evalue"], r["total"]),
            "taux_conformite": _pct(s["conforme"], applicables),
        })

    manquements = [
        {"referentiel": m.mesure.referentiel.code, "identifiant": m.mesure.identifiant, "intitule": m.mesure.intitule,
         "statut": m.statut, "justification": m.justification[:500]}
        for m in StatutMesure.objects.filter(projet=projet, statut__in=[StatutMesure.Statut.MANQUANT, StatutMesure.Statut.PARTIEL])
        .select_related("mesure__referentiel").order_by("statut", "mesure__referentiel__code", "mesure__identifiant")
    ]

    documents = DocumentAttendu.objects.filter(projet=projet).select_related("responsable__utilisateur", "responsable__role") \
        .annotate(nb_versions=Count("versions")).order_by("echeance", "intitule")
    liste_docs = [
        {"intitule": d.intitule, "statut": d.statut, "statut_libelle": d.get_statut_display(), "versions": d.nb_versions,
         "obligatoire": d.obligatoire, "echeance": d.echeance.isoformat() if d.echeance else None,
         "en_retard": bool(d.echeance and d.echeance < aujourd_hui and d.statut in ("attendu", "refuse")),
         "responsable": nom_acteur(d.responsable), "responsable_role": d.responsable.role.libelle if d.responsable else ""}
        for d in documents
    ]

    taches = Tache.objects.filter(projet=projet).select_related("mesure__referentiel", "responsable__utilisateur", "responsable__role")
    ouvertes = [t for t in taches if t.statut not in TACHES_CLOSES]
    ouvertes.sort(key=lambda t: (ORDRE_PRIORITE.get(t.priorite, 9), t.echeance or date.max))
    liste_taches = [
        {"titre": t.titre, "mesure": f"{t.mesure.referentiel.code} {t.mesure.identifiant}" if t.mesure else "",
         "statut": t.get_statut_display(), "priorite": t.priorite, "priorite_libelle": t.get_priorite_display(),
         "echeance": t.echeance.isoformat() if t.echeance else None,
         "en_retard": bool(t.echeance and t.echeance < aujourd_hui),
         "responsable": nom_acteur(t.responsable), "responsable_role": t.responsable.role.libelle if t.responsable else ""}
        for t in ouvertes
    ]

    risques = RisqueResiduel.objects.filter(projet=projet)
    derogations = Derogation.objects.filter(projet=projet)
    return {
        "genere_le": timezone.now().isoformat(),
        "projet": {
            "nom": projet.nom, "organisation": projet.organisation.nom, "type_bien": projet.get_type_bien_display(),
            "niveau_vise": projet.get_niveau_vise_display(), "ebios": projet.ebios_active,
        },
        "acteurs": [{"nom": nom_acteur(a), "role": a.role.libelle, "organisme": a.organisme}
                    for a in ActeurProjet.objects.filter(projet=projet).select_related("utilisateur", "role").order_by("role__libelle")],
        "referentiels": referentiels,
        "conformite": {
            "total": sum(r["total"] for r in referentiels),
            **{s.value: sum(r["statuts"][s.value] for r in referentiels) for s in STATUTS},
            "non_evalue": sum(r["statuts"]["non_evalue"] for r in referentiels),
        },
        "manquements": manquements[:MANQUEMENTS_MAX],
        "nb_manquements": len(manquements),
        "documents": {
            "liste": liste_docs,
            "total": len(liste_docs),
            "par_statut": {s: sum(1 for d in liste_docs if d["statut"] == s) for s in DocumentAttendu.Statut.values},
            "en_retard": sum(1 for d in liste_docs if d["en_retard"]),
        },
        "plan_action": {
            "ouvertes": len(ouvertes), "closes": len(taches) - len(ouvertes),
            "en_retard": sum(1 for t in liste_taches if t["en_retard"]),
            "par_priorite": {p: sum(1 for t in ouvertes if t.priorite == p) for p in ORDRE_PRIORITE},
            "liste": liste_taches[:TACHES_MAX],
        },
        "risques": {"total": risques.count(), "acceptes": risques.filter(statut=RisqueResiduel.Statut.ACCEPTE).count()},
        "derogations": {"total": derogations.count(), "acceptees": derogations.filter(statut=Derogation.Statut.ACCEPTEE).count()},
        "ia": {
            # Propositions de la dernière analyse documentaire terminée (les précédentes sont remplacées).
            "conclusions_a_valider": ResultatAnalyseMesure.objects.filter(
                projet=projet, statut_validation=StatutValidation.A_VALIDER,
                analyse=AnalyseIA.objects.filter(projet=projet, etat=AnalyseIA.Etat.TERMINEE,
                                                 type_analyse=AnalyseIA.Type.ANALYSE_DOCUMENTAIRE).order_by("-fin_le").first(),
            ).count(),
            "recommandations_acceptees": RecommandationIA.objects.filter(projet=projet, statut_validation=StatutValidation.VALIDE).count(),
        },
    }


def evolution(actuel, precedent):
    """Écarts entre deux instantanés (comparaison de versions du rapport)."""
    if not precedent:
        return None
    a, p = actuel["conformite"], precedent["conformite"]
    return {
        "conforme": a["conforme"] - p["conforme"], "manquant": a["manquant"] - p["manquant"],
        "partiel": a["partiel"] - p["partiel"], "non_evalue": a["non_evalue"] - p["non_evalue"],
        "taches_ouvertes": actuel["plan_action"]["ouvertes"] - precedent["plan_action"]["ouvertes"],
        "documents_valides": actuel["documents"]["par_statut"]["valide"] - precedent["documents"]["par_statut"]["valide"],
    }


def pour_ia(donnees):
    """Vue minimisée envoyée au fournisseur d'IA : aucun nom de personne ni d'organisation, rôles uniquement."""
    c = donnees["conformite"]
    evaluees, applicables = c["total"] - c["non_evalue"], c["total"] - c["non_applicable"]
    projet = donnees["projet"]
    return {
        # Libellés explicites et taux déjà calculés : le modèle n'a ni booléen à interpréter ni calcul à faire.
        # EBIOS RM n'est mentionné que s'il est activé, sans laisser croire que l'analyse est faite.
        "projet": {"type_bien": projet["type_bien"], "niveau_vise": projet["niveau_vise"]}
        | ({"ebios_rm": "méthode retenue pour le projet ; avancement des ateliers non renseigné"} if projet["ebios"] else {}),
        "synthese_chiffree": {
            "mesures_total": c["total"], "mesures_evaluees": evaluees, "taux_evaluation_global_pct": _pct(evaluees, c["total"]),
            "mesures_applicables": applicables, "mesures_conformes": c["conforme"],
            "taux_conformite_global_pct": _pct(c["conforme"], applicables),
        },
        "roles_acteurs": sorted({a["role"] for a in donnees["acteurs"]}),
        "referentiels": [{k: r[k] for k in ("nom", "total", "statuts", "taux_evaluation", "taux_conformite")} for r in donnees["referentiels"]],
        "conformite": donnees["conformite"],
        "manquements": [{k: m[k] for k in ("referentiel", "identifiant", "intitule", "statut")} for m in donnees["manquements"][:40]],
        "nb_manquements": donnees["nb_manquements"],
        "documents": {
            "total": donnees["documents"]["total"], "par_statut": donnees["documents"]["par_statut"],
            "en_retard": donnees["documents"]["en_retard"],
            "manquants": [d["intitule"] for d in donnees["documents"]["liste"] if d["statut"] in ("attendu", "refuse")][:30],
        },
        "plan_action": {k: donnees["plan_action"][k] for k in ("ouvertes", "closes", "en_retard", "par_priorite")}
        | {"prioritaires": [{"titre": t["titre"], "priorite": t["priorite"], "en_retard": t["en_retard"], "responsable": t["responsable_role"]}
                            for t in donnees["plan_action"]["liste"][:20]]},
        "risques": donnees["risques"], "derogations": donnees["derogations"], "ia": donnees["ia"],
        "evolution": donnees.get("evolution"),
    }
