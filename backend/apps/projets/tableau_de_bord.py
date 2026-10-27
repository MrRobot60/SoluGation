"""Agrégats du tableau de bord d'un projet, calculés pour l'utilisateur qui le consulte."""

from datetime import date, timedelta

from django.db.models import Count, Q

from apps.ai.models import AnalyseIA, ResultatAnalyseMesure
from apps.audit.models import JournalAudit
from apps.core.api.acces import (peut_administrer_projet, peut_decider_projet, peut_ecrire_projet,
                                 peut_prononcer_homologation)
from apps.core.models import StatutValidation
from apps.referentiels.models import Mesure
from apps.suivi.models import Tache

from .models import DocumentAttendu, StatutMesure

STATUTS = [StatutMesure.Statut.CONFORME, StatutMesure.Statut.PARTIEL, StatutMesure.Statut.MANQUANT,
           StatutMesure.Statut.NON_APPLICABLE]
TACHES_CLOSES = [Tache.Statut.TERMINEE, Tache.Statut.ABANDONNEE]
DOCS_EN_ATTENTE = [DocumentAttendu.Statut.ATTENDU, DocumentAttendu.Statut.REFUSE]
TAILLE_LISTE = 6


def _referentiels(projet):
    lignes = []
    for ref in projet.referentiels.order_by("code"):
        total = Mesure.objects.filter(referentiel=ref).count()
        par_statut = dict(
            StatutMesure.objects.filter(projet=projet, mesure__referentiel=ref, statut__in=STATUTS)
            .values_list("statut").annotate(n=Count("id"))
        )
        comptes = {s.value: par_statut.get(s.value, 0) for s in STATUTS}
        comptes["non_evalue"] = total - sum(comptes.values())
        lignes.append({"id": ref.id, "code": ref.code, "nom": ref.nom, "version": ref.version, "total": total,
                       "statuts": comptes, "nouvelle_version": ref.remplace_par_id is not None})
    return lignes


def _pour_vous(projet, utilisateur, aujourd_hui):
    elements = []
    taches = (Tache.objects.filter(projet=projet, responsable__utilisateur=utilisateur)
              .exclude(statut__in=TACHES_CLOSES).select_related("mesure__referentiel"))
    for t in taches:
        mesure = f"{t.mesure.referentiel.nom} {t.mesure.identifiant}" if t.mesure else ""
        elements.append({
            "type": "tache", "id": t.id, "titre": t.titre, "echeance": t.echeance,
            "detail": " · ".join(x for x in (mesure, t.preuve_attendue) if x),
            "en_retard": bool(t.echeance and t.echeance < aujourd_hui),
        })
    docs = DocumentAttendu.objects.filter(projet=projet, responsable__utilisateur=utilisateur, statut__in=DOCS_EN_ATTENTE)
    for d in docs.annotate(nb=Count("versions")):
        elements.append({
            "type": "document", "id": d.id, "titre": d.intitule, "echeance": d.echeance,
            "detail": "Refusé : nouvelle version attendue" if d.statut == DocumentAttendu.Statut.REFUSE
            else ("Aucune version déposée" if d.nb == 0 else f"{d.nb} version(s) déposée(s)"),
            "en_retard": bool(d.echeance and d.echeance < aujourd_hui),
        })
    if peut_ecrire_projet(utilisateur, projet):
        n = ResultatAnalyseMesure.objects.filter(projet=projet, statut_validation=StatutValidation.A_VALIDER).count()
        if n:
            elements.append({"type": "validation_ia", "id": None, "titre": f"{n} conclusion(s) de l'analyse IA à valider",
                             "detail": "L'IA propose, vous validez", "echeance": aujourd_hui, "en_retard": False})
    if peut_decider_projet(utilisateur, projet):
        from apps.risques.models import Derogation, RisqueResiduel

        if n := Derogation.objects.filter(projet=projet, statut=Derogation.Statut.DEMANDEE).count():
            elements.append({"type": "decision", "id": None, "titre": f"{n} dérogation(s) à décider", "lien": "risques?onglet=derogations",
                             "detail": "Accepter avec une date d'expiration, ou refuser en motivant", "echeance": aujourd_hui, "en_retard": False})
        risques = RisqueResiduel.objects.filter(projet=projet).exclude(statut=RisqueResiduel.Statut.CLOS)
        if n := risques.filter(statut=RisqueResiduel.Statut.IDENTIFIE).count():
            elements.append({"type": "decision", "id": None, "titre": f"{n} risque(s) résiduel(s) à statuer", "lien": "risques",
                             "detail": "Accepter formellement, ou traiter", "echeance": aujourd_hui, "en_retard": False})
        if n := risques.filter(date_revue__lt=aujourd_hui).count():
            elements.append({"type": "decision", "id": None, "titre": f"{n} risque(s) à revoir", "lien": "risques",
                             "detail": "Date de revue dépassée", "echeance": aujourd_hui, "en_retard": True})
    if projet.date_prochaine_revue and projet.statut != "archive" and peut_administrer_projet(utilisateur, projet) \
            and projet.date_prochaine_revue <= aujourd_hui + timedelta(days=30):
        retard = projet.date_prochaine_revue < aujourd_hui
        elements.append({"type": "decision", "id": None, "lien": "reglages", "echeance": projet.date_prochaine_revue, "en_retard": retard,
                         "titre": "Revue périodique en retard" if retard else "Revue périodique à préparer",
                         "detail": f"Prévue le {projet.date_prochaine_revue:%d/%m/%Y}"})
    # En retard d'abord, puis par échéance (sans échéance en dernier).
    elements.sort(key=lambda e: (not e["en_retard"], e["echeance"] or date.max))
    return elements


def _a_valider(projet):
    analyse = (AnalyseIA.objects.filter(projet=projet, resultats__statut_validation=StatutValidation.A_VALIDER)
               .distinct().order_by("-cree_le").prefetch_related("documents").first())
    if analyse is None:
        return None
    resultats = (analyse.resultats.filter(statut_validation=StatutValidation.A_VALIDER)
                 .select_related("mesure").order_by("mesure__ordre")[:TAILLE_LISTE])
    return {
        "analyse": analyse.id, "date": analyse.fin_le or analyse.cree_le,
        "documents": [d.nom_original for d in analyse.documents.all()],
        "total": analyse.resultats.filter(statut_validation=StatutValidation.A_VALIDER).count(),
        "conclusions": [{"id": r.id, "mesure": r.mesure.identifiant, "intitule": r.mesure.intitule,
                         "couverture": r.couverture} for r in resultats],
    }


def tableau_de_bord(projet, utilisateur, aujourd_hui=None):
    aujourd_hui = aujourd_hui or date.today()
    referentiels = _referentiels(projet)
    total = sum(r["total"] for r in referentiels)
    non_evalues = sum(r["statuts"]["non_evalue"] for r in referentiels)
    conformes = sum(r["statuts"]["conforme"] for r in referentiels)
    non_applicables = sum(r["statuts"]["non_applicable"] for r in referentiels)

    docs = DocumentAttendu.objects.filter(projet=projet)
    taches = Tache.objects.filter(projet=projet).exclude(statut__in=TACHES_CLOSES)
    prochain = docs.filter(statut__in=DOCS_EN_ATTENTE, echeance__gte=aujourd_hui).order_by("echeance").first()
    decision = docs.filter(type_document="Décision").order_by("echeance").values_list("echeance", flat=True).first()

    journal = JournalAudit.objects.filter(projet=projet).order_by("-id")[:TAILLE_LISTE]
    return {
        "projet": {
            "id": projet.id, "nom": projet.nom, "statut": projet.statut, "statut_libelle": projet.get_statut_display(),
            "type_bien": projet.type_bien, "type_bien_libelle": projet.get_type_bien_display(),
            "niveau_vise": projet.niveau_vise, "niveau_vise_libelle": projet.get_niveau_vise_display(),
            "ebios_active": projet.ebios_active, "date_prochaine_revue": projet.date_prochaine_revue,
            "lecture_seule": not peut_ecrire_projet(utilisateur, projet),
            "peut_decider": peut_decider_projet(utilisateur, projet),
            "peut_administrer": peut_administrer_projet(utilisateur, projet, meme_archive=True),
            "peut_prononcer": peut_prononcer_homologation(utilisateur, projet),
            "archive": projet.statut == "archive", "decision": projet.decision, "decision_libelle": projet.get_decision_display(),
            "date_decision": projet.date_decision, "date_fin_validite": projet.date_fin_validite,
            "decision_par": str(projet.decision_par or ""), "periodicite_revue_mois": projet.periodicite_revue_mois,
        },
        "referentiels": referentiels,
        "evaluation": {"evaluees": total - non_evalues, "total": total},
        "conformite": {"conformes": conformes, "applicables": total - non_applicables},
        "documents": {
            "attendus": docs.count(),
            "deposes": docs.filter(Q(versions__isnull=False) | Q(statut=DocumentAttendu.Statut.VALIDE)).distinct().count(),
            "valides": docs.filter(statut=DocumentAttendu.Statut.VALIDE).count(),
        },
        "taches": {
            "ouvertes": taches.count(),
            "en_retard": taches.filter(echeance__lt=aujourd_hui).count(),
        },
        "echeances": {
            "prochain_document": {"intitule": prochain.intitule, "echeance": prochain.echeance} if prochain else None,
            "decision": projet.date_decision or decision,
        },
        "pour_vous": _pour_vous(projet, utilisateur, aujourd_hui)[:TAILLE_LISTE],
        "a_valider": _a_valider(projet),
        "activite": [
            {"id": e.id, "horodatage": e.horodatage, "acteur": e.acteur_repr, "action": e.action,
             "objet_type": e.objet_type, "objet": e.objet_repr, "champs": sorted(e.donnees)[:8],
             "nb_checklist": len(e.donnees.get("checklist", []))}
            for e in journal
        ],
    }
