"""Réglages d'un projet : revue périodique (rappels), décision d'homologation, export calendrier (iCalendar)."""

import calendar
from datetime import date, datetime, timedelta, timezone as tz

from django.conf import settings
from rest_framework import serializers

from apps.audit.models import JournalAudit
from apps.suivi.models import Tache
from apps.suivi.notifications import acteurs_concernes, notifier

from .models import DocumentAttendu, Projet

RAPPEL_AVANT = timedelta(days=30)
STATUTS_MANUELS = (Projet.Statut.BROUILLON, Projet.Statut.EN_COURS, Projet.Statut.EN_ATTENTE_DECISION)
ROLES_REVUE = ("chef-projet", "rssi", "autorite-homologation")


def ajouter_mois(jour, mois):
    """jour + n mois, ramené au dernier jour du mois si besoin (31 janvier + 1 mois = 28 ou 29 février)."""
    m = jour.month - 1 + mois
    annee, m = jour.year + m // 12, m % 12 + 1
    return date(annee, m, min(jour.day, calendar.monthrange(annee, m)[1]))


class DecisionHomologationSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=Projet.Decision.choices)
    date_fin_validite = serializers.DateField(required=False, allow_null=True)
    commentaire = serializers.CharField(required=False, allow_blank=True, max_length=4000)

    def validate(self, attrs):
        if attrs["decision"] != Projet.Decision.REFUS:
            fin = attrs.get("date_fin_validite")
            if not fin or fin <= date.today():
                raise serializers.ValidationError({"date_fin_validite": "Une homologation a une date de fin de validité future."})
        elif not attrs.get("commentaire", "").strip():
            raise serializers.ValidationError({"commentaire": "Motivez le refus d'homologation."})
        return attrs


def appliquer_decision(projet, utilisateur, donnees):
    projet.decision, projet.decision_par, projet.date_decision = donnees["decision"], utilisateur, date.today()
    projet.date_fin_validite = donnees.get("date_fin_validite") if donnees["decision"] != Projet.Decision.REFUS else None
    projet.statut = Projet.Statut.REFUSE if donnees["decision"] == Projet.Decision.REFUS else Projet.Statut.HOMOLOGUE
    if projet.statut == Projet.Statut.HOMOLOGUE:
        # Prochaine revue : selon la périodicité, et au plus tard à la fin de validité.
        projet.date_prochaine_revue = min(ajouter_mois(date.today(), projet.periodicite_revue_mois), projet.date_fin_validite)
    projet.save()


def rappeler_revues(aujourd_hui=None):
    """Rappel 30 jours avant la revue périodique, puis rappel de retard ; une seule fois par date de revue."""
    aujourd_hui = aujourd_hui or date.today()
    envoyes = 0
    for projet in (Projet.objects.exclude(statut=Projet.Statut.ARCHIVE).filter(date_prochaine_revue__isnull=False)
                   .select_related("organisation", "cree_par")):
        echeance = projet.date_prochaine_revue
        if echeance < aujourd_hui and projet.rappel_retard_pour != echeance:
            titre, champ = f"Revue périodique en retard (prévue le {echeance:%d/%m/%Y})", "rappel_retard_pour"
        elif aujourd_hui <= echeance <= aujourd_hui + RAPPEL_AVANT and projet.rappel_revue_pour != echeance:
            titre, champ = f"Revue périodique le {echeance:%d/%m/%Y}", "rappel_revue_pour"
        else:
            continue
        notifier(projet, auteur=None, type_evenement="revue.rappel", titre=titre,
                 message="Revoyez l'état des lieux, les risques résiduels et les dérogations, puis fixez la revue suivante.",
                 lien=f"/projets/{projet.pk}/reglages", destinataires=acteurs_concernes(projet, roles=ROLES_REVUE))
        setattr(projet, champ, echeance)
        projet.save(update_fields=[champ])
        JournalAudit.enregistrer(organisation=projet.organisation, action=JournalAudit.Action.MODIFICATION, objet=projet,
                                 projet=projet, donnees={"rappel": champ, "date_revue": echeance.isoformat()})
        envoyes += 1
    return envoyes


def _texte_ics(texte):
    return str(texte).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def _plier(ligne):
    """Lignes iCalendar limitées à 75 octets (RFC 5545), continuées par une espace."""
    octets, morceaux = ligne.encode(), []
    while len(octets) > 75:
        coupe = 75 if not morceaux else 74
        while coupe and (octets[coupe] & 0xC0) == 0x80:  # ne pas couper un caractère UTF-8
            coupe -= 1
        morceaux.append(octets[:coupe].decode())
        octets = octets[coupe:]
    morceaux.append(octets.decode())
    return "\r\n ".join(morceaux)


def evenements(projet):
    """Échéances du projet : tâches ouvertes, documents attendus, revue, dérogations, fin de validité, ateliers."""
    from apps.ebios.models import AtelierEBIOS
    from apps.risques.models import Derogation

    base = f"{settings.FRONTEND_URL}/projets/{projet.pk}"
    for t in Tache.objects.filter(projet=projet, echeance__isnull=False).exclude(statut__in=["terminee", "abandonnee"]):
        yield f"tache-{t.pk}", t.echeance, f"Tâche : {t.titre}", f"{base}/plan-action?tache={t.pk}"
    for d in DocumentAttendu.objects.filter(projet=projet, echeance__isnull=False).exclude(statut__in=["valide", "non_applicable"]):
        yield f"document-{d.pk}", d.echeance, f"Document attendu : {d.intitule}", f"{base}/documents"
    if projet.date_prochaine_revue:
        yield f"revue-{projet.pk}", projet.date_prochaine_revue, "Revue périodique de l'homologation", f"{base}/reglages"
    if projet.date_fin_validite:
        yield f"validite-{projet.pk}", projet.date_fin_validite, "Fin de validité de l'homologation", f"{base}/reglages"
    for d in Derogation.objects.filter(projet=projet, statut=Derogation.Statut.ACCEPTEE, date_expiration__isnull=False):
        yield f"derogation-{d.pk}", d.date_expiration, "Fin d'une dérogation", f"{base}/risques?onglet=derogations"
    if projet.ebios_active:
        for a in AtelierEBIOS.objects.filter(projet=projet, date_atelier__isnull=False):
            yield f"atelier-{a.pk}", a.date_atelier, f"EBIOS RM : {a.get_numero_display()}", f"{base}/ebios?atelier={a.numero}"


def calendrier_ics(projet):
    horodatage = datetime.now(tz.utc).strftime("%Y%m%dT%H%M%SZ")
    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SoluGation//Homologation//FR", "CALSCALE:GREGORIAN",
              f"X-WR-CALNAME:{_texte_ics(f'SoluGation · {projet.nom}')}"]
    for uid, jour, titre, url in evenements(projet):
        lignes += ["BEGIN:VEVENT", f"UID:{uid}@solugation", f"DTSTAMP:{horodatage}", f"DTSTART;VALUE=DATE:{jour:%Y%m%d}",
                   f"DTEND;VALUE=DATE:{jour + timedelta(days=1):%Y%m%d}", f"SUMMARY:{_texte_ics(f'{projet.nom} — {titre}')}",
                   f"URL:{url}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    lignes.append("END:VCALENDAR")
    return "\r\n".join(_plier(l) for l in lignes) + "\r\n"
