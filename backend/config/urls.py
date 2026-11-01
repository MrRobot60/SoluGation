from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def sante(_request):
    return JsonResponse({"statut": "ok", "service": "SoluGation"})


def a_propos(_request):
    """Licence et code source, affichés à tous les utilisateurs : l'AGPL-3.0 (article 13) impose à qui propose en ligne
    une version modifiée d'en offrir le code source à ses utilisateurs."""
    return JsonResponse({"logiciel": "SoluGation", "licence": "AGPL-3.0-or-commercial",
                         "licence_libelle": "GNU AGPL-3.0 ou licence commerciale",
                         "code_source": settings.SOLUGATION_URL_CODE_SOURCE})


admin.site.site_header = "SoluGation"
admin.site.site_title = "SoluGation"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/sante/", sante),
    path("api/a-propos/", a_propos),
    path("api/", include("config.api")),
]
