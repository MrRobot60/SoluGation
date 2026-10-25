from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Organisation, Role, Utilisateur


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("nom", "secteur", "ia_activee", "active", "cree_le")
    list_filter = ("secteur", "ia_activee", "active")
    search_fields = ("nom", "siret")
    readonly_fields = ("prefixe_stockage", "cree_le", "modifie_le")
    prepopulated_fields = {"slug": ("nom",)}


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("libelle", "code", "portee", "lecture_seule", "organisation")
    list_filter = ("portee", "lecture_seule")
    search_fields = ("libelle", "code")


class UtilisateurCreationForm(UserCreationForm):
    class Meta:
        model = Utilisateur
        fields = ("email", "organisation", "role")


class UtilisateurChangeForm(UserChangeForm):
    class Meta:
        model = Utilisateur
        fields = "__all__"

    def clean(self):
        donnees = super().clean()
        role = donnees.get("role")
        if role and role.organisation_id not in (None, getattr(donnees.get("organisation"), "id", None)):
            raise forms.ValidationError("Rôle propre à une autre organisation.")
        return donnees


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    form = UtilisateurChangeForm
    add_form = UtilisateurCreationForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "organisation", "role", "is_active", "is_staff")
    list_filter = ("organisation", "role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identité", {"fields": ("first_name", "last_name", "fonction")}),
        ("Organisation", {"fields": ("organisation", "role")}),
        ("Droits plateforme", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "organisation", "role", "password1", "password2")}),
    )
