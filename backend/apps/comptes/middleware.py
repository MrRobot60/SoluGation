"""Application de la double authentification à chaque requête (API et admin Django), côté serveur."""

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponseRedirect, JsonResponse

from .double_auth import SESSION_VERIFIEE, active, politique, requise

# Accessibles à un compte qui doit encore configurer sa double authentification.
LIBRES = ("/api/auth/", "/api/sante/")


class DoubleAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        chemin = request.path
        if request.user.is_authenticated and chemin.startswith(("/api/", "/admin/")):
            admin = chemin.startswith("/admin/")
            if active(request.user) and not request.session.get(SESSION_VERIFIEE):
                # Session ouverte sans le second facteur (formulaire de l'admin Django, session antérieure à
                # l'activation) : fermée. On se reconnecte par SoluGation, qui demande le code.
                logout(request)
                if admin:
                    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/connexion")
            elif requise(request.user, politique()) and not active(request.user) and not chemin.startswith(LIBRES):
                if admin:
                    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/compte")
                return JsonResponse({"detail": "Activez la double authentification (Mon compte) pour continuer.",
                                     "code": "double_auth_a_configurer"}, status=403)
        return self.get_response(request)
