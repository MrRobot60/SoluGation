from django.contrib import admin

from apps.core.admin import ProjetAdmin

from . import models

for modele in (
    models.AtelierEBIOS, models.ValeurMetier, models.BienSupport, models.EvenementRedoute, models.EcartSocle,
    models.SourceRisque, models.ObjectifVise, models.CoupleSROV, models.PartiePrenante, models.ScenarioStrategique,
    models.CheminAttaque, models.MesureEcosysteme, models.ScenarioOperationnel, models.RisqueEBIOS,
    models.MesureTraitement,
):
    admin.site.register(modele, type(f"{modele.__name__}Admin", (ProjetAdmin,), {"list_display": ("__str__", "projet")}))
