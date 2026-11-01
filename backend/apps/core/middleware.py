"""Adresse IP réelle du client derrière le proxy de production (journal d'audit, limitation des connexions).
Activé seulement si SOLUGATION_PROXY_DE_CONFIANCE=True : sans proxy devant, l'en-tête serait falsifiable."""

from django.conf import settings


class AdresseClientMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.SOLUGATION_PROXY_DE_CONFIANCE:
            # Chaque proxy de confiance ajoute l'adresse de qui lui parle : avec N proxys, le client est la N-ième entrée
            # en partant de la fin. Ce qui précède a pu être écrit par le client lui-même : jamais lu.
            entrees = [e.strip() for e in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if e.strip()]
            if entrees:
                request.META["REMOTE_ADDR"] = entrees[-min(settings.SOLUGATION_NB_PROXYS, len(entrees))]
        return self.get_response(request)
