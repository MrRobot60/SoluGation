from django.contrib import admin

from apps.core.admin import ProjetAdmin

from .models import Derogation, RisqueResiduel


@admin.register(RisqueResiduel)
class RisqueResiduelAdmin(ProjetAdmin):
    list_display = ("intitule", "projet", "gravite", "vraisemblance", "statut", "origine")
    list_filter = ProjetAdmin.list_filter + ("statut", "origine")


@admin.register(Derogation)
class DerogationAdmin(ProjetAdmin):
    list_display = ("__str__", "projet", "statut", "decidee_par", "date_decision", "date_expiration")
    list_filter = ProjetAdmin.list_filter + ("statut",)
