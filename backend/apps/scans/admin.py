from django.contrib import admin

from apps.core.admin import FichierAdmin, ProjetAdmin

from .models import ConstatScan, ImportScan


@admin.register(ImportScan)
class ImportScanAdmin(FichierAdmin):
    list_display = ("nom_original", "outil", "projet", "etat", "date_scan")
    list_filter = ProjetAdmin.list_filter + ("outil", "etat")


@admin.register(ConstatScan)
class ConstatScanAdmin(ProjetAdmin):
    list_display = ("titre", "severite", "cvss", "hote", "port", "statut", "projet")
    list_filter = ProjetAdmin.list_filter + ("severite", "statut")
    search_fields = ("titre", "hote")
