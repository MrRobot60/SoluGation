from django.contrib import admin

from apps.core.admin import ProjetAdmin, TenantAdmin

from .models import ActeurProjet, DocumentAttendu, Projet, ProjetReferentiel, StatutMesure


class ProjetReferentielInline(admin.TabularInline):
    model = ProjetReferentiel
    fields = ("referentiel",)
    extra = 0
    max_num = 3


class ActeurProjetInline(admin.TabularInline):
    model = ActeurProjet
    fields = ("utilisateur", "nom", "email", "role")
    extra = 0


@admin.register(Projet)
class ProjetModelAdmin(TenantAdmin):
    list_display = ("nom", "organisation", "type_bien", "niveau_vise", "statut", "ebios_active", "decision")
    list_filter = ("organisation", "statut", "type_bien", "ebios_active")
    search_fields = ("nom",)
    inlines = [ProjetReferentielInline, ActeurProjetInline]


@admin.register(ActeurProjet)
class ActeurProjetAdmin(ProjetAdmin):
    list_display = ("__str__", "projet", "role")


@admin.register(StatutMesure)
class StatutMesureAdmin(ProjetAdmin):
    list_display = ("mesure", "projet", "statut", "evalue_par")
    list_filter = ProjetAdmin.list_filter + ("statut",)
    autocomplete_fields = ("projet", "mesure")


@admin.register(DocumentAttendu)
class DocumentAttenduAdmin(ProjetAdmin):
    list_display = ("intitule", "projet", "responsable", "echeance", "statut")
    list_filter = ProjetAdmin.list_filter + ("statut",)
    autocomplete_fields = ("projet", "mesures")
