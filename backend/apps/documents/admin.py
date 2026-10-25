from django.contrib import admin

from apps.core.admin import FichierAdmin

from .models import DocumentDepose, Preuve


@admin.register(DocumentDepose)
class DocumentDeposeAdmin(FichierAdmin):
    list_display = ("nom_original", "version", "document_attendu", "projet", "sha256", "depose_le")


@admin.register(Preuve)
class PreuveAdmin(FichierAdmin):
    list_display = ("titre", "version", "projet", "sha256", "date_validite", "depose_le")
    autocomplete_fields = ("projet", "mesures")
