"""Rendu PDF du rapport avec WeasyPrint, depuis le texte stocké et l'instantané figé : aucune requête sur les
données vivantes, aucun appel IA. Un rapport non validé sort marqué « Brouillon »."""

import re
from datetime import date, datetime
from pathlib import Path

from django.template.loader import render_to_string
from weasyprint import HTML

RESSOURCES = Path(__file__).resolve().parent / "ressources"
STATUTS = [("conforme", "Conforme"), ("partiel", "Partiel"), ("manquant", "Manquant"), ("non_applicable", "Non applicable"),
           ("non_evalue", "Non évalué")]


def blocs(texte):
    """Paragraphes et listes à puces (lignes « - ») ; tout le reste est du texte brut, échappé par le gabarit.
    Espace insécable avant « % » et les ponctuations doubles, comme en typographie française."""
    texte = re.sub(r"\s+([%:;!?»])", "\u00a0\\1", texte).replace("« ", "«\u00a0")
    resultat = []
    for paragraphe in re.split(r"\n\s*\n", texte.strip()):
        lignes = [l.strip() for l in paragraphe.splitlines() if l.strip()]
        texte_libre, puces = [], []
        for ligne in lignes:
            if re.match(r"^[-•*]\s+", ligne):
                puces.append(re.sub(r"^[-•*]\s+", "", ligne))
            else:
                if puces:
                    resultat += [{"type": "p", "texte": " ".join(texte_libre)}] if texte_libre else []
                    resultat.append({"type": "ul", "items": puces})
                    texte_libre, puces = [], []
                texte_libre.append(ligne)
        if texte_libre:
            resultat.append({"type": "p", "texte": " ".join(texte_libre)})
        if puces:
            resultat.append({"type": "ul", "items": puces})
    return resultat


def chaine_css(texte):
    """Texte inséré dans une chaîne CSS `content: "..."` (en-têtes de page) : ni balise, ni sortie de chaîne."""
    texte = re.sub(r"[<>\x00-\x1f]", " ", str(texte))
    return texte.replace("\\", "\\\\").replace('"', '\\"')


def _date(valeur):
    if not valeur:
        return ""
    if isinstance(valeur, str):
        valeur = datetime.fromisoformat(valeur)
    return (valeur.date() if isinstance(valeur, datetime) else valeur).strftime("%d/%m/%Y")


def rendre(rapport, analyse=None):
    d = rapport.donnees
    contexte = {
        "rapport": rapport,
        "brouillon": rapport.statut_validation != "valide",
        "d": d,
        "date_donnees": _date(d.get("genere_le")),
        "date_validation": _date(rapport.valide_le),
        "sections": [{**s, "blocs": blocs(s["texte"])} for s in rapport.sections],
        "statuts": STATUTS,
        "referentiels": [{**r, "segments": [(cle, libelle, r["statuts"][cle], 100 * r["statuts"][cle] / r["total"] if r["total"] else 0)
                                            for cle, libelle in STATUTS]} for r in d["referentiels"]],
        "evolution": d.get("evolution"),
        "evolution_visible": any((d.get("evolution") or {}).values()),
        "redaction_ia": analyse is not None and any(s["source"] in ("ia", "modifie") for s in rapport.sections),
        "analyse": analyse,
        "taches": [{**t, "echeance_fr": _date(t["echeance"])} for t in d["plan_action"]["liste"]],
        "registre_risques": [{**r, "revue_fr": _date(r["date_revue"]), "accepte_fr": _date(r["accepte_le"])} for r in d.get("registre", {}).get("risques", [])],
        "registre_derogations": [{**x, "expiration_fr": _date(x["date_expiration"])} for x in d.get("registre", {}).get("derogations", [])],
        # Lettres des annexes : E registre, puis EBIOS RM s'il est activé, puis acteurs.
        "lettre_ebios": "F", "lettre_acteurs": "G" if d.get("ebios") else "F",
        "documents": [{**x, "echeance_fr": _date(x["echeance"])} for x in d["documents"]["liste"]],
        "aujourd_hui": date.today().strftime("%d/%m/%Y"),
        "matrice_ebios": [(g, [(d["ebios"]["matrice"].get(f"{g}-{v}", 0)) for v in range(1, 5)]) for g in range(4, 0, -1)] if d.get("ebios") else [],
        "css": {"projet": chaine_css(d["projet"]["nom"]), "valide_par": chaine_css(rapport.valide_par or "")},
    }
    html = render_to_string("rapports/rapport.html", contexte)
    return HTML(string=html, base_url=str(RESSOURCES)).write_pdf()
