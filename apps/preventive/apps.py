from django.apps import AppConfig


class PreventiveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.preventive"
    verbose_name = "Maintenance préventive"
