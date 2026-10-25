"""Bases d'admin. L'admin Django est réservé au staff plateforme ; les utilisateurs clients passent par l'API."""

from django.contrib import admin


class TenantAdmin(admin.ModelAdmin):
    list_filter = ("organisation",)
    readonly_fields = ("organisation", "cree_le", "modifie_le")
    list_select_related = ("organisation",)


class ProjetAdmin(TenantAdmin):
    list_filter = ("organisation", "projet")
    list_select_related = ("organisation", "projet")
    autocomplete_fields = ("projet",)


class ValidationAdmin(ProjetAdmin):
    """Conclusions IA : la validation passe par l'appli (traçée au journal), pas par l'admin."""

    readonly_fields = ProjetAdmin.readonly_fields + ("statut_validation", "valide_par", "valide_le")
    list_filter = ProjetAdmin.list_filter + ("statut_validation",)


class FichierAdmin(ProjetAdmin):
    readonly_fields = ProjetAdmin.readonly_fields + ("nom_original", "type_mime", "taille", "sha256", "depose_par", "depose_le")

    def get_readonly_fields(self, request, obj=None):
        champs = super().get_readonly_fields(request, obj)
        return champs + ("fichier",) if obj else champs
