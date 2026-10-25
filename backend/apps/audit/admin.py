from django.contrib import admin

from .models import JournalAudit


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    """Consultation seule : aucun ajout, aucune modification, aucune suppression."""

    list_display = ("horodatage", "organisation", "acteur_repr", "action", "objet_type", "objet_repr", "projet")
    list_filter = ("organisation", "action", "objet_type")
    search_fields = ("objet_repr", "acteur_repr", "objet_id")
    date_hierarchy = "horodatage"
    list_select_related = ("organisation", "projet")

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
