from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("horodatage", "utilisateur", "action", "entite", "entite_id")
    list_filter = ("action", "entite", "horodatage")
    search_fields = ("utilisateur__username", "action", "entite")
    readonly_fields = ("horodatage",)
