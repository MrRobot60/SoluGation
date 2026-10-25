from django.contrib import admin

from apps.core.admin import ProjetAdmin, TenantAdmin

from .models import ActionPlan, Commentaire, Notification, Reunion, Tache


class TacheInline(admin.TabularInline):
    model = Tache
    fields = ("titre", "responsable", "echeance", "statut", "priorite")
    extra = 0
    show_change_link = True


@admin.register(ActionPlan)
class ActionPlanAdmin(ProjetAdmin):
    list_display = ("titre", "projet")
    inlines = [TacheInline]


@admin.register(Tache)
class TacheAdmin(ProjetAdmin):
    list_display = ("titre", "projet", "responsable", "echeance", "statut", "priorite", "origine")
    list_filter = ProjetAdmin.list_filter + ("statut", "priorite", "origine")
    search_fields = ("titre",)


@admin.register(Commentaire)
class CommentaireAdmin(ProjetAdmin):
    list_display = ("auteur", "projet", "cree_le")


@admin.register(Reunion)
class ReunionAdmin(ProjetAdmin):
    list_display = ("titre", "projet", "debut", "statut")


@admin.register(Notification)
class NotificationAdmin(TenantAdmin):
    list_display = ("titre", "destinataire", "type_evenement", "lue_le", "mail_envoye_le")
