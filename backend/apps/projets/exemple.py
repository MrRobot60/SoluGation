"""Projet d'exemple de la visite guidée : un par utilisateur, créé à sa première visite, sans mail ni appel IA.
Il se manipule comme un vrai projet (et s'archive quand on n'en veut plus)."""

from datetime import date, timedelta

from django.db import transaction

from apps.audit.models import JournalAudit
from apps.comptes.models import Role
from apps.referentiels.models import Referentiel
from apps.suivi.services import generer_plan_action

from .checklist import generer_checklist
from .models import ActeurProjet, Projet, ProjetReferentiel, StatutMesure

NOM = "Exemple — Intranet RH"
CODES_PREFERES = ("hygiene-anssi", "rgs", "owasp-asvs")
MESURES_EVALUEES = 16  # par référentiel : assez pour un tableau de bord parlant, peu de tâches générées
CYCLE = [StatutMesure.Statut.CONFORME] * 3 + [StatutMesure.Statut.PARTIEL, StatutMesure.Statut.CONFORME,
                                             StatutMesure.Statut.MANQUANT, StatutMesure.Statut.NON_APPLICABLE]


def _referentiels():
    publics = Referentiel.objects.filter(organisation=None)
    preferes = list(publics.filter(code__in=CODES_PREFERES))
    return preferes or list(publics.order_by("code")[:3])


def _nom_libre(utilisateur):
    pris = set(Projet.objects.filter(organisation=utilisateur.organisation, nom__startswith=NOM).values_list("nom", flat=True))
    if NOM not in pris:
        return NOM
    for nom in (f"{NOM} ({utilisateur})", *(f"{NOM} ({utilisateur}) {i}" for i in range(2, 100))):
        if nom[:200] not in pris:
            return nom[:200]
    raise RuntimeError("Aucun nom libre pour le projet d'exemple.")


def projet_exemple(utilisateur):
    """Renvoie le projet d'exemple de l'utilisateur (non archivé), en le créant au besoin."""
    existant = Projet.objects.filter(organisation=utilisateur.organisation, exemple=True, cree_par=utilisateur) \
        .exclude(statut=Projet.Statut.ARCHIVE).first()
    if existant:
        return existant
    with transaction.atomic():
        projet = Projet.objects.create(
            organisation=utilisateur.organisation, nom=_nom_libre(utilisateur), exemple=True, cree_par=utilisateur,
            description="Projet fictif pour découvrir SoluGation : modifiez, déposez, testez librement, puis archivez-le.",
            type_bien=Projet.TypeBien.APPLICATION, niveau_vise=Projet.NiveauVise.STANDARD, statut=Projet.Statut.EN_COURS,
            ebios_active=True, notifications_actives=False, date_prochaine_revue=date.today() + timedelta(days=365),
        )
        roles = {r.code: r for r in Role.objects.filter(organisation=None, portee=Role.Portee.PROJET)}
        ActeurProjet.objects.create(projet=projet, utilisateur=utilisateur, role=roles["chef-projet"])
        if "autorite-homologation" in roles:
            # Contact fictif (domaine réservé .invalid) ; les notifications du projet sont de toute façon coupées.
            ActeurProjet.objects.create(projet=projet, nom="Direction (exemple)", email="autorite@exemple.invalid",
                                        organisme="Organisation fictive", role=roles["autorite-homologation"])
        for ref in _referentiels():
            ProjetReferentiel.objects.create(projet=projet, referentiel=ref)
            for i, mesure in enumerate(ref.mesures.order_by("ordre")[:MESURES_EVALUEES]):
                StatutMesure.objects.create(projet=projet, mesure=mesure, statut=CYCLE[i % len(CYCLE)], evalue_par=utilisateur,
                                            justification="Évaluation d'exemple.")
        generer_checklist(projet)
        generer_plan_action(projet)
        JournalAudit.enregistrer(utilisateur.organisation, JournalAudit.Action.CREATION, projet, acteur=utilisateur,
                                 projet=projet, donnees={"source": "visite guidée"})
    return projet
