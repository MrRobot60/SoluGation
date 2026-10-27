"""Notifications : une entrée dans l'appli pour chaque utilisateur concerné, et un mail (y compris aux contacts
externes sans compte). Les mails partent après validation de la transaction : jamais pour une écriture annulée.
L'auteur de la modification n'est pas notifié de sa propre action. Le projet peut couper ses notifications."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.projets.models import ActeurProjet

from .models import Notification

journal = logging.getLogger(__name__)


def acteurs_concernes(projet, *, responsable=None, roles=("chef-projet",), en_plus=()):
    """Le responsable de l'objet, les acteurs des rôles indiqués, et d'éventuels utilisateurs supplémentaires."""
    acteurs = list(ActeurProjet.objects.filter(projet=projet, role__code__in=roles).select_related("utilisateur"))
    if responsable is not None:
        acteurs.append(responsable)
    destinataires = {}
    for a in acteurs:
        if a.utilisateur_id:
            destinataires[f"u:{a.utilisateur_id}"] = a.utilisateur
        elif a.email:
            destinataires[f"e:{a.email.lower()}"] = a.email
    for u in en_plus:
        destinataires[f"u:{u.pk}"] = u
    return list(destinataires.values())


def notifier(projet, *, auteur, type_evenement, titre, message, lien, destinataires, mail=True):
    """`auteur=None` : message du système (rappel), envoyé à tous les destinataires.
    `mail=False` : notification dans l'appli seulement (quand un autre mail part déjà, ex. invitation .ics)."""
    if not projet.notifications_actives:
        return []
    utilisateurs = [d for d in destinataires if not isinstance(d, str) and (auteur is None or d.pk != auteur.pk) and d.is_active
                    and d.organisation_id == projet.organisation_id]
    externes = [d for d in destinataires if isinstance(d, str) and (auteur is None or d.lower() != auteur.email.lower())]
    notifications = [
        Notification.objects.create(organisation=projet.organisation, destinataire=u, projet=projet,
                                    type_evenement=type_evenement, titre=titre[:200], message=message, lien=lien)
        for u in utilisateurs
    ]
    adresses = [u.email for u in utilisateurs] + externes
    if adresses and mail:
        ids = [n.pk for n in notifications]
        transaction.on_commit(lambda: _envoyer(projet, auteur, titre, message, lien, adresses, ids))
    return notifications


def _envoyer(projet, auteur, titre, message, lien, adresses, ids_notifications):
    contexte = {
        "titre": titre, "message": message, "projet": projet.nom, "auteur": str(auteur) if auteur else "SoluGation",
        "lien": f"{settings.FRONTEND_URL}{lien}", "logo": f"{settings.FRONTEND_URL}/marque/icone-128.png",
    }
    sujet = f"[SoluGation] {projet.nom} : {titre}"[:200]
    texte = render_to_string("mails/notification.txt", contexte)
    html = render_to_string("mails/notification.html", contexte)
    envoyes = []
    for adresse in adresses:  # un mail par destinataire : aucune adresse n'est exposée aux autres
        try:
            mail = EmailMultiAlternatives(sujet, texte, settings.DEFAULT_FROM_EMAIL, [adresse])
            mail.attach_alternative(html, "text/html")
            mail.send()
            envoyes.append(adresse)
        except Exception:  # un relais en panne ne doit pas casser l'action de l'utilisateur
            journal.exception("Échec d'envoi de notification à un destinataire du projet %s", projet.pk)
    Notification.objects.filter(pk__in=ids_notifications, destinataire__email__in=envoyes).update(
        mail_envoye_le=timezone.now())
