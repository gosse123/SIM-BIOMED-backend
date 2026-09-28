from django.contrib import admin

from .models import Equipment, Localisation, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("nom",)


@admin.register(Localisation)
class LocalisationAdmin(admin.ModelAdmin):
    list_display = ("batiment", "etage", "salle")


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = (
        "num_inventaire",
        "nom",
        "type_equipement",
        "service",
        "etat_operationnel",
        "niveau_criticite",
    )
    list_filter = ("etat_operationnel", "niveau_criticite", "service")
    search_fields = ("num_inventaire", "nom", "num_serie")
