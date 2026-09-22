from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Etablissement, DemandeAcces, Notification


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "is_active", "profil_complete")
    list_filter = ("role", "is_active", "profil_complete")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("SIM-BIOMED", {"fields": ("role", "matricule", "etablissement", "profil_complete")}),
    )


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ("nom", "actif", "created_at")
    list_filter = ("actif",)


@admin.register(DemandeAcces)
class DemandeAccesAdmin(admin.ModelAdmin):
    list_display = ("nom_complet", "email", "role_souhaite", "statut", "date_creation", "traite_par")
    list_filter = ("statut", "role_souhaite")
    readonly_fields = ("date_creation", "date_traitement")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("titre", "destinataire", "lu", "date_creation")
    list_filter = ("lu",)
    readonly_fields = ("date_creation",)
