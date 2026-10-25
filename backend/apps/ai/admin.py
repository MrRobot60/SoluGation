from django.contrib import admin

from apps.core.admin import ValidationAdmin

from .models import AnalyseIA, RecommandationIA, ResultatAnalyseMesure


@admin.register(AnalyseIA)
class AnalyseIAAdmin(ValidationAdmin):
    list_display = ("type_analyse", "projet", "etat", "statut_validation", "modele", "cree_le")
    list_filter = ValidationAdmin.list_filter + ("type_analyse", "etat")


@admin.register(ResultatAnalyseMesure)
class ResultatAnalyseMesureAdmin(ValidationAdmin):
    list_display = ("mesure", "couverture", "projet", "statut_validation", "confiance")
    list_filter = ValidationAdmin.list_filter + ("couverture",)


@admin.register(RecommandationIA)
class RecommandationIAAdmin(ValidationAdmin):
    list_display = ("__str__", "mesure", "projet", "statut_validation")
