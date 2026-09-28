from django.contrib import admin

from .models import MaintenancePlan, MaintenancePreventive


@admin.register(MaintenancePlan)
class MaintenancePlanAdmin(admin.ModelAdmin):
    list_display = ("nom", "type_equipement", "frequence", "delai_jours")


@admin.register(MaintenancePreventive)
class MaintenancePreventiveAdmin(admin.ModelAdmin):
    list_display = ("id", "plan", "equipement", "statut", "date_planifiee", "date_effective")
    list_filter = ("statut",)
    raw_id_fields = ("plan", "equipement", "realisee_par")
