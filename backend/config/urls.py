from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def sante(_request):
    return JsonResponse({"statut": "ok", "service": "SoluGation"})


admin.site.site_header = "SoluGation"
admin.site.site_title = "SoluGation"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/sante/", sante),
]
