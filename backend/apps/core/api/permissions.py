from rest_framework.permissions import SAFE_METHODS, BasePermission

from .acces import est_admin_organisation, peut_ecrire_projet


class MembreOrganisation(BasePermission):
    """Authentifié, rattaché à une organisation active. Le staff plateforme sans organisation n'a pas accès à l'API."""

    message = "Compte non rattaché à une organisation active."

    def has_permission(self, request, view):
        u = request.user
        return bool(u.is_authenticated and u.is_active and u.organisation_id and u.organisation.active)


class EcritureSelonRole(BasePermission):
    """Lecture libre (dans le périmètre filtré), écriture refusée aux rôles lecture seule."""

    message = "Action non autorisée pour votre rôle."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or not request.user.est_lecture_seule

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        projet = obj if obj.__class__.__name__ == "Projet" else getattr(obj, "projet", None)
        return projet is not None and peut_ecrire_projet(request.user, projet)


class AdminOrganisation(BasePermission):
    message = "Réservé à l'administrateur de l'organisation."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or est_admin_organisation(request.user)
