"""Règles d'accès centralisées. Toute requête API passe par ces fonctions : une seule source de vérité
pour l'isolation entre organisations.

- Un utilisateur ne voit que les données de SON organisation (jamais d'exception, staff compris).
- Dans son organisation, il voit les projets dont il est acteur ; l'administrateur d'organisation les voit tous.
- Un rôle `lecture_seule` (auditeur), au niveau organisation ou projet, interdit toute écriture.
- Les décisions (valider ou refuser une pièce, statuer sur une conclusion de l'IA) sont réservées au RSSI
  et à l'autorité d'homologation du projet, ainsi qu'à l'administrateur d'organisation.
- Les réglages du projet (identité, référentiels, acteurs, options, archivage) : chef de projet, RSSI,
  autorité d'homologation, administrateur d'organisation.
- La décision d'homologation : l'autorité d'homologation du projet, et elle seule.
- Un projet archivé est en lecture seule pour tous (seul le désarchivage reste possible)."""

from apps.comptes.models import Role
from apps.projets.models import ActeurProjet, Projet

ROLE_ADMIN = "admin"
ROLES_DECISIONNAIRES = ("rssi", "autorite-homologation")
ROLES_ADMINISTRATEURS_PROJET = ("chef-projet", "rssi", "autorite-homologation")
ROLE_AUTORITE = "autorite-homologation"


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
    if utilisateur.est_lecture_seule or projet.organisation_id != utilisateur.organisation_id or est_archive(projet):
        return False
    if est_admin_organisation(utilisateur):
        return True
    roles = ActeurProjet.objects.filter(projet=projet, utilisateur=utilisateur).values_list("role__lecture_seule", flat=True)
    return any(lecture_seule is False for lecture_seule in roles)


def est_archive(projet):
    return projet.statut == Projet.Statut.ARCHIVE


def _a_un_role(utilisateur, projet, roles):
    return ActeurProjet.objects.filter(projet=projet, utilisateur=utilisateur, role__code__in=roles, role__lecture_seule=False).exists()


def peut_administrer_projet(utilisateur, projet, meme_archive=False):
    """Réglages du projet. `meme_archive=True` : seul cas d'écriture sur un projet archivé (le désarchiver)."""
    if utilisateur.est_lecture_seule or projet.organisation_id != utilisateur.organisation_id:
        return False
    if est_archive(projet) and not meme_archive:
        return False
    return est_admin_organisation(utilisateur) or _a_un_role(utilisateur, projet, ROLES_ADMINISTRATEURS_PROJET)


def peut_prononcer_homologation(utilisateur, projet):
    if utilisateur.est_lecture_seule or projet.organisation_id != utilisateur.organisation_id or est_archive(projet):
        return False
    return _a_un_role(utilisateur, projet, (ROLE_AUTORITE,))


def peut_decider_projet(utilisateur, projet):
    if utilisateur.est_lecture_seule or projet.organisation_id != utilisateur.organisation_id or est_archive(projet):
        return False
    if est_admin_organisation(utilisateur):
        return True
    return ActeurProjet.objects.filter(
        projet=projet, utilisateur=utilisateur, role__code__in=ROLES_DECISIONNAIRES, role__lecture_seule=False
    ).exists()
