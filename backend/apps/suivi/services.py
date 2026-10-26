"""Plan d'action : un manquement (mesure « manquant » ou « partiel ») = une tâche, jamais deux tâches ouvertes
pour la même mesure. La tâche est créée à l'évaluation ; elle est close par un humain, jamais automatiquement."""

from datetime import date, timedelta

from apps.projets.models import ActeurProjet, StatutMesure

from .models import ActionPlan, Tache

STATUTS_MANQUEMENT = (StatutMesure.Statut.MANQUANT, StatutMesure.Statut.PARTIEL)
TACHES_CLOSES = (Tache.Statut.TERMINEE, Tache.Statut.ABANDONNEE)
DELAIS = {Tache.Priorite.HAUTE: 30, Tache.Priorite.MOYENNE: 60}
ROLES_RESPONSABLES = ("rssi", "chef-projet")


def plan_du_projet(projet):
    plan, _ = ActionPlan.objects.get_or_create(projet=projet)
    return plan


def responsable_par_defaut(projet):
    for code in ROLES_RESPONSABLES:
        acteur = ActeurProjet.objects.filter(projet=projet, role__code=code).order_by("cree_le").first()
        if acteur:
            return acteur
    return None


def tache_pour_manquement(evaluation, aujourd_hui=None):
    """Crée la tâche d'un manquement si aucune tâche ouverte n'existe pour cette mesure. Renvoie la tâche créée ou None."""
    if evaluation.statut not in STATUTS_MANQUEMENT:
        return None
    projet, mesure = evaluation.projet, evaluation.mesure
    if Tache.objects.filter(projet=projet, mesure=mesure).exclude(statut__in=TACHES_CLOSES).exists():
        return None
    priorite = Tache.Priorite.HAUTE if evaluation.statut == StatutMesure.Statut.MANQUANT else Tache.Priorite.MOYENNE
    etat = "non satisfaite" if evaluation.statut == StatutMesure.Statut.MANQUANT else "partiellement satisfaite"
    return Tache.objects.create(
        projet=projet, plan=plan_du_projet(projet), mesure=mesure, titre=mesure.intitule[:300],
        description=f"Mesure {mesure.identifiant} ({mesure.referentiel.nom}) {etat}."
                    + (f"\nConstat : {evaluation.justification}" if evaluation.justification else ""),
        preuve_attendue=f"Preuve de mise en œuvre de la mesure {mesure.identifiant} (procédure, configuration, capture).",
        responsable=responsable_par_defaut(projet), priorite=priorite,
        echeance=(aujourd_hui or date.today()) + timedelta(days=DELAIS[priorite]),
        origine=Tache.Origine.ANALYSE_IA if evaluation.resultat_analyse_id else Tache.Origine.EVALUATION,
        resultat_analyse=evaluation.resultat_analyse,
    )


def generer_plan_action(projet):
    """Rattrapage : une tâche pour chaque manquement déjà évalué qui n'en a pas encore."""
    evaluations = StatutMesure.objects.filter(projet=projet, statut__in=STATUTS_MANQUEMENT).select_related(
        "mesure__referentiel", "resultat_analyse")
    return [t for t in (tache_pour_manquement(e) for e in evaluations.order_by("mesure__referentiel", "mesure__ordre")) if t]
