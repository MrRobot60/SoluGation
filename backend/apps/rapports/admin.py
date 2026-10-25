from django.contrib import admin

from apps.core.admin import ValidationAdmin

from .models import Rapport


@admin.register(Rapport)
class RapportAdmin(ValidationAdmin):
    list_display = ("titre", "version", "projet", "statut_validation", "pdf_genere_le")
    readonly_fields = ValidationAdmin.readonly_fields + ("fichier_pdf", "sha256_pdf", "pdf_genere_le")
