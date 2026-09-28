from django.contrib import admin

from .models import Intervention


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ("id", "equipement", "type_intervention", "statut", "realisee_par", "date_debut")
    list_filter = ("statut", "type_intervention")
    raw_id_fields = ("panne", "equipement", "realisee_par")
