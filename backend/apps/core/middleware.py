"""Adresse IP réelle du client derrière le proxy de production (journal d'audit, limitation des connexions).
Activé seulement si SOLUGATION_PROXY_DE_CONFIANCE=True : sans proxy devant, l'en-tête serait falsifiable."""

from django.conf import settings


class AdresseClientMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.SOLUGATION_PROXY_DE_CONFIANCE:
            # Le proxy (Caddy) remplace l'en-tête reçu par l'adresse du client : la dernière entrée est la sienne.
            transmis = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
            if transmis:
                request.META["REMOTE_ADDR"] = transmis
        return self.get_response(request)
