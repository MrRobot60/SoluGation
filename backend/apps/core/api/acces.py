"""Règles d'accès centralisées. Toute requête API passe par ces fonctions : une seule source de vérité
pour l'isolation entre organisations.

- Un utilisateur ne voit que les données de SON organisation (jamais d'exception, staff compris).
- Dans son organisation, il voit les projets dont il est acteur ; l'administrateur d'organisation les voit tous.
- Un rôle `lecture_seule` (auditeur), au niveau organisation ou projet, interdit toute écriture.
- Les décisions (valider ou refuser une pièce, statuer sur une conclusion de l'IA) sont réservées au RSSI
  et à l'autorité d'homologation du projet, ainsi qu'à l'administrateur d'organisation."""

from apps.comptes.models import Role
from apps.projets.models import ActeurProjet, Projet

ROLE_ADMIN = "admin"
ROLES_DECISIONNAIRES = ("rssi", "autorite-homologation")


def est_admin_organisation(utilisateur):
    return bool(
        utilisateur.organisation_id and utilisateur.role and utilisateur.role.code == ROLE_ADMIN
        and utilisateur.role.portee == Role.Portee.ORGANISATION
    )


def projets_accessibles(utilisateur):
    if not utilisateur.is_authenticated or not utilisateur.organisation_id:
        return Projet.objects.none()
    qs = Projet.objects.filter(organisation_id=utilisateur.organisation_id)
    if est_admin_organisation(utilisateur):
        return qs
    return qs.filter(acteurprojet__utilisateur=utilisateur).distinct()


def peut_ecrire_projet(utilisateur, projet):
    """Écriture : membre non auditeur, et acteur du projet sans rôle lecture seule (ou admin d'organisation)."""
    if utilisateur.est_lecture_seule or projet.organisation_id != utilisateur.organisation_id:
        return False
    if est_admin_organisation(utilisateur):
        return True
    roles = ActeurProjet.objects.filter(projet=projet, utilisateur=utilisateur).values_list("role__lecture_seule", flat=True)
    return any(lecture_seule is False for lecture_seule in roles)


def peut_decider_projet(utilisateur, projet):
    if utilisateur.est_lecture_seule or projet.organisation_id != utilisateur.organisation_id:
        return False
    if est_admin_organisation(utilisateur):
        return True
    return ActeurProjet.objects.filter(
        projet=projet, utilisateur=utilisateur, role__code__in=ROLES_DECISIONNAIRES, role__lecture_seule=False
    ).exists()
