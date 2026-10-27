"""Réunions : invitations iCalendar (acceptées par Outlook, Google Agenda, Apple Calendrier) envoyées par mail
après validation de la transaction, rappel la veille, diffusion du compte rendu validé.

Une invitation par destinataire, qui ne nomme que lui comme participant : aucune adresse n'est exposée aux
autres (comme pour les notifications). Les noms des participants figurent dans la description."""

import logging
from datetime import timedelta, timezone as tz

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from apps.projets.reglages import plier_ics, texte_ics

from .models import Reunion
from .notifications import notifier

journal = logging.getLogger(__name__)


def adresse_acteur(acteur):
    return (acteur.utilisateur.email if acteur.utilisateur_id else acteur.email) or ""


def lien(reunion):
    return f"/projets/{reunion.projet_id}/reunions?reunion={reunion.pk}"


def _horodatage(valeur):
    return valeur.astimezone(tz.utc).strftime("%Y%m%dT%H%M%SZ")


def nom_sans_adresse(acteur):
    """Nom affichable d'un participant sans jamais révéler d'adresse mail (à défaut de nom : son rôle)."""
    if acteur.utilisateur_id:
        nom = acteur.utilisateur.get_full_name().strip()
    else:
        nom = acteur.nom.strip()
    return nom or acteur.role.libelle


def ics_invitation(reunion, destinataire, annulation=False):
    """Invitation (METHOD:REQUEST) ou annulation (METHOD:CANCEL) pour un destinataire."""
    noms = ", ".join(nom_sans_adresse(a) for a in reunion.participants.select_related("utilisateur", "role"))
    description = "\n\n".join(x for x in (
        f"Projet : {reunion.projet.nom}", f"Ordre du jour :\n{reunion.ordre_du_jour}" if reunion.ordre_du_jour else "",
        f"Participants : {noms}" if noms else "", f"Visio : {reunion.lien_visio}" if reunion.lien_visio else "",
        f"Dans SoluGation : {settings.FRONTEND_URL}{lien(reunion)}") if x)
    expediteur = settings.DEFAULT_FROM_EMAIL.split("<")[-1].rstrip(">").strip()
    lignes = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SoluGation//Reunions//FR", f"METHOD:{'CANCEL' if annulation else 'REQUEST'}",
        "BEGIN:VEVENT", f"UID:reunion-{reunion.pk}@solugation", f"SEQUENCE:{reunion.sequence}", f"DTSTAMP:{_horodatage(timezone.now())}",
        f"DTSTART:{_horodatage(reunion.debut)}", f"DTEND:{_horodatage(reunion.fin)}",
        f"SUMMARY:{texte_ics(reunion.titre)}", f"DESCRIPTION:{texte_ics(description)}",
        f"LOCATION:{texte_ics(reunion.lieu or reunion.lien_visio)}",
        f"ORGANIZER;CN={texte_ics(reunion.organisateur.get_full_name().strip() or 'SoluGation')}:mailto:{expediteur}",
        f"ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=FALSE:mailto:{destinataire}",
        f"STATUS:{'CANCELLED' if annulation else 'CONFIRMED'}", "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(plier_ics(l) for l in lignes) + "\r\n"


def _envoyer_invitations(reunion_id, annulation):
    reunion = Reunion.objects.select_related("projet", "organisateur").get(pk=reunion_id)
    debut = timezone.localtime(reunion.debut)
    sujet = f"[SoluGation] {'Annulée : ' if annulation else ''}{reunion.titre} — {debut:%d/%m/%Y %H:%M}"[:200]
    texte = (f"{'Réunion annulée' if annulation else 'Invitation'} : {reunion.titre}\n{debut:%A %d/%m/%Y, %H:%M}"
             f"{' · ' + reunion.lieu if reunion.lieu else ''}\nProjet : {reunion.projet.nom}\n\n{reunion.ordre_du_jour}\n\n"
             f"{settings.FRONTEND_URL}{lien(reunion)}")
    for acteur in reunion.participants.select_related("utilisateur"):
        adresse = adresse_acteur(acteur)
        if not adresse:
            continue
        try:
            mail = EmailMultiAlternatives(sujet, texte, settings.DEFAULT_FROM_EMAIL, [adresse])
            mail.attach("invitation.ics", ics_invitation(reunion, adresse, annulation),
                        f"text/calendar; method={'CANCEL' if annulation else 'REQUEST'}; charset=UTF-8")
            mail.send()
        except Exception:  # un relais en panne ne doit pas casser la planification
            journal.exception("Échec d'envoi d'invitation pour la réunion %s", reunion_id)


def inviter(reunion, annulation=False):
    """Envoie (ou renvoie, ou annule) l'invitation à chaque participant, après validation de la transaction."""
    transaction.on_commit(lambda: _envoyer_invitations(reunion.pk, annulation))


def rappeler_reunions(maintenant=None):
    """Rappel dans l'appli et par mail, environ 24 h avant chaque réunion planifiée (une seule fois)."""
    maintenant = maintenant or timezone.now()
    envoyes = 0
    for r in (Reunion.objects.filter(statut=Reunion.Statut.PLANIFIEE, rappel_envoye_le__isnull=True,
                                     debut__gt=maintenant, debut__lte=maintenant + timedelta(hours=24))
              .select_related("projet")):
        debut = timezone.localtime(r.debut)
        destinataires = [a.utilisateur if a.utilisateur_id else a.email for a in r.participants.select_related("utilisateur")]
        notifier(r.projet, auteur=None, type_evenement="reunion.rappel", titre=f"Réunion demain : {r.titre}",
                 message=f"{debut:%d/%m/%Y à %H:%M}{' · ' + r.lieu if r.lieu else ''}{' · ' + r.lien_visio if r.lien_visio else ''}",
                 lien=lien(r), destinataires=[d for d in destinataires if d])
        r.rappel_envoye_le = maintenant
        r.save(update_fields=["rappel_envoye_le"])
        envoyes += 1
    return envoyes
