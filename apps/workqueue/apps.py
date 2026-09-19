from django.apps import AppConfig


class WorkqueueConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.workqueue"
    verbose_name = "File de travail"
