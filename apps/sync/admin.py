from django.contrib import admin
from .models import OfflineOperation


@admin.register(OfflineOperation)
class OfflineOperationAdmin(admin.ModelAdmin):
    list_display = (
        "offline_id",
        "method",
        "url",
        "statut",
        "response_status",
        "user",
        "executed_at",
    )
    list_filter = ("statut", "method")
    search_fields = ("offline_id", "url")
    readonly_fields = (
        "offline_id",
        "user",
        "method",
        "url",
        "body",
        "statut",
        "response_status",
        "response_body",
        "error_message",
        "executed_at",
        "created_at",
    )
    ordering = ["-executed_at"]
