"""Comparaison de deux versions du rapport d'état des lieux, à partir de leurs instantanés figés : aucune donnée
vivante n'intervient, la comparaison est reproductible. Écarts chiffrés, manquements apparus ou résolus,
documents et tâches, registre des risques, et différentiel mot à mot du texte de chaque section."""

import difflib
import re

SEGMENTS_MAX = 4000


def _ecart(avant, apres):
    return {"avant": avant, "apres": apres, "ecart": (apres - avant) if isinstance(avant, (int, float)) and isinstance(apres, (int, float)) else None}


def chiffres(a, b):
    ca, cb = a["conformite"], b["conformite"]
    lignes = {f"conformite.{k}": _ecart(ca.get(k, 0), cb.get(k, 0)) for k in ("conforme", "partiel", "manquant", "non_applicable", "non_evalue")}
    lignes["manquements"] = _ecart(a["nb_manquements"], b["nb_manquements"])
    lignes["taches.ouvertes"] = _ecart(a["plan_action"]["ouvertes"], b["plan_action"]["ouvertes"])
    lignes["taches.en_retard"] = _ecart(a["plan_action"]["en_retard"], b["plan_action"]["en_retard"])
    lignes["taches.closes"] = _ecart(a["plan_action"]["closes"], b["plan_action"]["closes"])
    for statut in ("valide", "depose", "attendu", "refuse"):
        lignes[f"documents.{statut}"] = _ecart(a["documents"]["par_statut"].get(statut, 0), b["documents"]["par_statut"].get(statut, 0))
    lignes["risques.total"] = _ecart(a["risques"]["total"], b["risques"]["total"])
    lignes["risques.acceptes"] = _ecart(a["risques"]["acceptes"], b["risques"]["acceptes"])
    lignes["derogations.acceptees"] = _ecart(a["derogations"]["acceptees"], b["derogations"]["acceptees"])
    return lignes


def referentiels(a, b):
    avant = {r["code"]: r for r in a["referentiels"]}
    resultat = []
    for r in b["referentiels"]:
        p = avant.get(r["code"])
        resultat.append({"code": r["code"], "nom": r["nom"], "nouveau": p is None,
                         "taux_conformite": _ecart(p["taux_conformite"] if p else 0, r["taux_conformite"]),
                         "taux_evaluation": _ecart(p["taux_evaluation"] if p else 0, r["taux_evaluation"])})
    resultat += [{"code": c, "nom": r["nom"], "retire": True} for c, r in avant.items() if c not in {x["code"] for x in b["referentiels"]}]
    return resultat


def manquements(a, b):
    """Par mesure : apparus, résolus (plus manquants ni partiels), aggravés (partiel → manquant), améliorés."""
    def cle(m):
        return m["referentiel"], m["identifiant"]

    def vue(m):
        return {"referentiel": m["referentiel"], "identifiant": m["identifiant"], "intitule": m["intitule"], "statut": m["statut"]}

    avant, apres = {cle(m): m for m in a["manquements"]}, {cle(m): m for m in b["manquements"]}
    tronque = a["nb_manquements"] > len(a["manquements"]) or b["nb_manquements"] > len(b["manquements"])
    return {
        "apparus": [vue(m) for k, m in apres.items() if k not in avant],
        "resolus": [vue(m) for k, m in avant.items() if k not in apres],
        "aggraves": [vue(apres[k]) for k in apres.keys() & avant.keys() if avant[k]["statut"] == "partiel" and apres[k]["statut"] == "manquant"],
        "ameliores": [vue(apres[k]) for k in apres.keys() & avant.keys() if avant[k]["statut"] == "manquant" and apres[k]["statut"] == "partiel"],
        "partiel": tronque,  # listes limitées aux manquements figés dans chaque instantané
    }


def documents(a, b):
    avant = {d["intitule"]: d for d in a["documents"]["liste"]}
    return [{"intitule": d["intitule"], "avant": avant[d["intitule"]]["statut_libelle"] if d["intitule"] in avant else None,
             "apres": d["statut_libelle"]}
            for d in b["documents"]["liste"] if d["intitule"] not in avant or avant[d["intitule"]]["statut"] != d["statut"]]


def taches(a, b):
    avant, apres = {t["titre"] for t in a["plan_action"]["liste"]}, {t["titre"] for t in b["plan_action"]["liste"]}
    return {"nouvelles": sorted(apres - avant), "sorties": sorted(avant - apres)}  # sorties : closes ou abandonnées


def registre(a, b):
    ra, rb = a.get("registre") or {}, b.get("registre") or {}
    if not ra and not rb:
        return None
    avant = {r["intitule"]: r for r in ra.get("risques", [])}
    risques = [{"intitule": r["intitule"], "avant": avant[r["intitule"]]["statut"] if r["intitule"] in avant else None, "apres": r["statut"]}
               for r in rb.get("risques", []) if r["intitule"] not in avant or avant[r["intitule"]]["statut"] != r["statut"]]
    return {"risques": risques}


def differentiel(texte_a, texte_b):
    """Différentiel mot à mot : [{type: egal | ajout | retrait, texte}], segments contigus fusionnés."""
    mots_a, mots_b = re.findall(r"\S+|\s+", texte_a or ""), re.findall(r"\S+|\s+", texte_b or "")
    segments = []
    for operation, i1, i2, j1, j2 in difflib.SequenceMatcher(a=mots_a, b=mots_b, autojunk=False).get_opcodes():
        if operation == "equal":
            segments.append(("egal", "".join(mots_a[i1:i2])))
        else:
            if i2 > i1:
                segments.append(("retrait", "".join(mots_a[i1:i2])))
            if j2 > j1:
                segments.append(("ajout", "".join(mots_b[j1:j2])))
    return [{"type": t, "texte": x} for t, x in segments[:SEGMENTS_MAX]]


def comparer(rapport_a, rapport_b):
    """`rapport_a` : la version la plus ancienne, `rapport_b` : la plus récente."""
    a, b = rapport_a.donnees, rapport_b.donnees
    sections_a = {s["cle"]: s for s in rapport_a.sections}
    sections = []
    for s in rapport_b.sections:
        avant = sections_a.get(s["cle"], {}).get("texte", "")
        sections.append({"cle": s["cle"], "titre": s["titre"], "identique": avant == s["texte"], "segments": differentiel(avant, s["texte"])})
    def resume(r):
        return {"id": str(r.pk), "version": r.version, "statut_validation": r.statut_validation,
                "date_donnees": r.donnees.get("genere_le"), "valide_le": r.valide_le}

    return {
        "avant": resume(rapport_a), "apres": resume(rapport_b),
        "chiffres": chiffres(a, b), "referentiels": referentiels(a, b), "manquements": manquements(a, b),
        "documents": documents(a, b), "taches": taches(a, b), "registre": registre(a, b), "sections": sections,
    }
