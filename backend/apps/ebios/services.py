"""EBIOS RM : ateliers d'un projet, socle pré-rempli depuis la conformité, synthèse (avancement, alertes de
cohérence, matrice des risques, cartographie de la menace) et passage de l'atelier 5 au plan d'action et au
registre des risques résiduels."""

from datetime import date, timedelta

from apps.projets.models import StatutMesure
from apps.risques.models import RisqueResiduel
from apps.suivi.models import Tache
from apps.suivi.services import plan_du_projet, responsable_par_defaut

from .models import (
    AtelierEBIOS, BienSupport, CheminAttaque, CoupleSROV, EcartSocle, EvenementRedoute, MesureEcosysteme,
    MesureTraitement, ObjectifVise, PartiePrenante, RisqueEBIOS, ScenarioOperationnel, ScenarioStrategique,
    SourceRisque, ValeurMetier,
)

# Seuils par défaut de la cartographie de la menace (ajustables plus tard par organisation).
SEUIL_DANGER = 2.5
SEUIL_CONTROLE = 0.9
DELAI_MESURE = timedelta(days=90)


def ateliers(projet):
    """Les cinq ateliers existent dès l'activation : créés à la première consultation."""
    existants = {a.numero: a for a in AtelierEBIOS.objects.filter(projet=projet)}
    manquants = [n for n in AtelierEBIOS.Numero.values if n not in existants]
    if manquants:
        # Deux requêtes simultanées (synthèse et liste des ateliers) : la contrainte d'unicité départage sans erreur.
        AtelierEBIOS.objects.bulk_create([AtelierEBIOS(projet=projet, organisation_id=projet.organisation_id, numero=n) for n in manquants],
                                         ignore_conflicts=True)
        existants = {a.numero: a for a in AtelierEBIOS.objects.filter(projet=projet)}
    return [existants[n] for n in sorted(existants)]


def preremplir_socle(projet):
    """Écarts au socle déduits des évaluations de conformité (manquant → non appliqué, partiel → restrictions).
    N'écrase rien : une mesure déjà présente dans le socle est ignorée."""
    deja = set(EcartSocle.objects.filter(projet=projet, mesure__isnull=False).values_list("mesure_id", flat=True))
    crees = []
    for s in (StatutMesure.objects.filter(projet=projet, statut__in=[StatutMesure.Statut.MANQUANT, StatutMesure.Statut.PARTIEL])
              .exclude(mesure_id__in=deja).select_related("mesure__referentiel").order_by("mesure__referentiel__code", "mesure__identifiant")):
        crees.append(EcartSocle.objects.create(
            projet=projet, referentiel=s.mesure.referentiel, mesure=s.mesure,
            intitule=f"{s.mesure.identifiant} — {s.mesure.intitule}"[:300],
            etat=EcartSocle.Etat.NON_APPLIQUE if s.statut == StatutMesure.Statut.MANQUANT else EcartSocle.Etat.RESTRICTIONS,
            justification=s.justification,
        ))
    return crees


def zone_menace(niveau):
    return "danger" if niveau >= SEUIL_DANGER else "controle" if niveau >= SEUIL_CONTROLE else "veille"


def alertes(projet):
    """Incohérences entre ateliers, à corriger avant de conclure (la navigation reste libre)."""
    a = []
    vm = ValeurMetier.objects.filter(projet=projet)
    if not vm.exists():
        a.append({"atelier": 1, "texte": "Aucune valeur métier : commencez par les processus et informations essentiels."})
    if n := vm.filter(evenements_redoutes__isnull=True).count():
        a.append({"atelier": 1, "texte": f"{n} valeur(s) métier sans événement redouté."})
    if n := vm.filter(biens_supports__isnull=True).count():
        a.append({"atelier": 1, "texte": f"{n} valeur(s) métier sans bien support."})
    couples = CoupleSROV.objects.filter(projet=projet)
    if couples.exists() and not couples.filter(retenu=True).exists():
        a.append({"atelier": 2, "texte": "Aucun couple SR/OV retenu : les scénarios stratégiques n'ont pas de point de départ."})
    if n := couples.filter(retenu=True, scenarios__isnull=True).count():
        a.append({"atelier": 3, "texte": f"{n} couple(s) SR/OV retenu(s) sans scénario stratégique."})
    if n := ScenarioStrategique.objects.filter(projet=projet, evenements_redoutes__isnull=True).count():
        a.append({"atelier": 3, "texte": f"{n} scénario(s) stratégique(s) sans événement redouté."})
    if n := ScenarioStrategique.objects.filter(projet=projet, chemins__isnull=True).count():
        a.append({"atelier": 3, "texte": f"{n} scénario(s) stratégique(s) sans chemin d'attaque."})
    if n := CheminAttaque.objects.filter(projet=projet, scenarios_operationnels__isnull=True).count():
        a.append({"atelier": 4, "texte": f"{n} chemin(s) d'attaque sans scénario opérationnel."})
    if n := ScenarioStrategique.objects.filter(projet=projet, risques__isnull=True).count():
        a.append({"atelier": 5, "texte": f"{n} scénario(s) stratégique(s) pas encore repris en risque."})
    risques = RisqueEBIOS.objects.filter(projet=projet)
    if n := risques.filter(option_traitement="").count():
        a.append({"atelier": 5, "texte": f"{n} risque(s) sans option de traitement."})
    if n := risques.filter(option_traitement__in=["reduire", "transferer", "eviter"], mesures_traitement__isnull=True).count():
        a.append({"atelier": 5, "texte": f"{n} risque(s) à réduire, transférer ou éviter sans mesure de traitement."})
    return a


def _matrice(risques, residuelle=False):
    cases = {}
    for r in risques:
        g = r.gravite_residuelle if residuelle else r.gravite
        v = r.vraisemblance_residuelle if residuelle else r.vraisemblance
        if g and v:
            cases.setdefault(f"{g}-{v}", []).append({"id": str(r.pk), "intitule": r.intitule})
    return cases


def synthese(projet):
    risques = list(RisqueEBIOS.objects.filter(projet=projet).order_by("-gravite", "-vraisemblance"))
    parties = PartiePrenante.objects.filter(projet=projet).order_by("nom")
    comptes = {
        "valeurs_metier": ValeurMetier.objects.filter(projet=projet).count(),
        "biens_supports": BienSupport.objects.filter(projet=projet).count(),
        "evenements_redoutes": EvenementRedoute.objects.filter(projet=projet).count(),
        "ecarts_socle": EcartSocle.objects.filter(projet=projet).exclude(etat=EcartSocle.Etat.APPLIQUE).count(),
        "sources_risque": SourceRisque.objects.filter(projet=projet).count(),
        "objectifs_vises": ObjectifVise.objects.filter(projet=projet).count(),
        "couples_retenus": CoupleSROV.objects.filter(projet=projet, retenu=True).count(),
        "parties_prenantes": parties.count(),
        "scenarios_strategiques": ScenarioStrategique.objects.filter(projet=projet).count(),
        "chemins_attaque": CheminAttaque.objects.filter(projet=projet).count(),
        "mesures_ecosysteme": MesureEcosysteme.objects.filter(projet=projet).count(),
        "scenarios_operationnels": ScenarioOperationnel.objects.filter(projet=projet).count(),
        "risques": len(risques),
        "mesures_traitement": MesureTraitement.objects.filter(projet=projet).count(),
    }
    return {
        "ateliers": [{"numero": a.numero, "libelle": a.get_numero_display(), "statut": a.statut, "date_atelier": a.date_atelier,
                      "id": str(a.pk)} for a in ateliers(projet)],
        "comptes": comptes,
        "alertes": alertes(projet),
        "matrice": {"initiale": _matrice(risques), "residuelle": _matrice(risques, residuelle=True)},
        "cartographie": {
            "seuils": {"danger": SEUIL_DANGER, "controle": SEUIL_CONTROLE},
            "parties": [{"id": str(p.pk), "nom": p.nom, "categorie": p.categorie, "niveau_menace": p.niveau_menace,
                         "zone": zone_menace(p.niveau_menace), "critique": p.critique} for p in parties],
        },
    }


def tache_pour_mesure(mesure):
    """Une mesure de traitement (PACS) devient une tâche du plan d'action, avec ses risques en description."""
    projet = mesure.projet
    risques = ", ".join(r.intitule for r in mesure.risques.all()[:10])
    tache = Tache.objects.create(
        projet=projet, plan=plan_du_projet(projet), titre=mesure.intitule[:300], origine=Tache.Origine.EBIOS,
        description=(mesure.description + ("\n\n" if mesure.description else "") + (f"Risques traités (EBIOS RM) : {risques}." if risques else "")).strip(),
        responsable=mesure.responsable or responsable_par_defaut(projet),
        echeance=mesure.echeance or date.today() + DELAI_MESURE, priorite=Tache.Priorite.HAUTE,
        preuve_attendue="Preuve de mise en œuvre de la mesure de traitement (procédure, configuration, capture).",
    )
    mesure.tache = tache
    mesure.save(update_fields=["tache", "modifie_le"])
    return tache


def synchroniser_risque_residuel(risque):
    """Risque accepté → inscrit au registre des risques résiduels (à faire accepter formellement par
    l'autorité d'homologation). Une autre option retire l'inscription tant qu'elle n'a pas été acceptée."""
    existant = RisqueResiduel.objects.filter(projet=risque.projet, risque_ebios=risque).first()
    if risque.option_traitement == RisqueEBIOS.Option.ACCEPTER:
        valeurs = {"intitule": risque.intitule, "gravite": risque.gravite_residuelle or risque.gravite,
                   "vraisemblance": risque.vraisemblance_residuelle or risque.vraisemblance}
        if existant is None:
            return RisqueResiduel.objects.create(projet=risque.projet, risque_ebios=risque, origine=RisqueResiduel.Origine.EBIOS,
                                                 description="Risque issu d'EBIOS RM, option de traitement « accepter ».", **valeurs)
        if existant.statut == RisqueResiduel.Statut.IDENTIFIE:
            for champ, v in valeurs.items():
                setattr(existant, champ, v)
            existant.save()
        return existant
    if existant is not None and existant.statut == RisqueResiduel.Statut.IDENTIFIE:
        existant.delete()
    return None

