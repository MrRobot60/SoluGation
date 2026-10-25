from django.contrib import admin

from .models import CorrespondanceMesure, Mesure, Referentiel


class MesureInline(admin.TabularInline):
    model = Mesure
    fields = ("identifiant", "intitule", "categorie", "ordre")
    extra = 0
    show_change_link = True


@admin.register(Referentiel)
class ReferentielAdmin(admin.ModelAdmin):
    list_display = ("nom", "version", "code", "organisation", "licence", "texte_embarque", "nb_mesures", "date_import")
    list_filter = ("licence", "texte_embarque", "actif", "organisation")
    search_fields = ("nom", "code")
    readonly_fields = ("date_import", "empreinte_source", "cree_le", "modifie_le")
    inlines = [MesureInline]

    @admin.display(description="mesures")
    def nb_mesures(self, obj):
        return obj.mesures.count()


@admin.register(Mesure)
class MesureAdmin(admin.ModelAdmin):
    list_display = ("identifiant", "intitule", "categorie", "referentiel")
    list_filter = ("referentiel",)
    search_fields = ("identifiant", "intitule")
    autocomplete_fields = ("parent",)
    list_select_related = ("referentiel",)


@admin.register(CorrespondanceMesure)
class CorrespondanceMesureAdmin(admin.ModelAdmin):
    list_display = ("mesure_source", "type_correspondance", "mesure_cible", "origine", "organisation")
    list_filter = ("type_correspondance", "origine")
    autocomplete_fields = ("mesure_source", "mesure_cible")
