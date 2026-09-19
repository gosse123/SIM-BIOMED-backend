from django.contrib import admin
from .models import Panne


@admin.register(Panne)
class PanneAdmin(admin.ModelAdmin):
    list_display = ("id", "equipement", "statut", "niveau_criticite", "signale_par", "date_signalement")
    list_filter = ("statut", "niveau_criticite")
    raw_id_fields = ("equipement", "signale_par", "qualifiee_par", "diagnostique_par", "cloturee_par")
