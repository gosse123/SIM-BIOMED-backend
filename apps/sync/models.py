from django.db import models
from apps.accounts.models import User


class OfflineOperation(models.Model):
    """Trace des operations executees hors ligne pour idempotence."""

    class StatutExecution(models.TextChoices):
        EN_COURS = "EN_COURS", "En cours"
        OK = "OK", "Succes"
        ERREUR = "ERREUR", "Erreur"

    offline_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="ID hors ligne (X-Offline-Id)",
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="offline_operations"
    )
    method = models.CharField(max_length=10, verbose_name="HTTP method")
    url = models.CharField(max_length=500, verbose_name="URL demandee")
    body = models.JSONField(null=True, blank=True, verbose_name="Corps de la requete")
    statut = models.CharField(
        max_length=15,
        choices=StatutExecution.choices,
        default=StatutExecution.EN_COURS,
    )
    response_status = models.IntegerField(
        null=True, blank=True, verbose_name="HTTP status de la reponse"
    )
    response_body = models.JSONField(
        null=True, blank=True, verbose_name="Corps de la reponse"
    )
    error_message = models.TextField(blank=True, verbose_name="Message d'erreur")
    executed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "operation hors ligne"
        verbose_name_plural = "operations hors ligne"
        ordering = ["-executed_at"]

    def __str__(self):
        return f"{self.offline_id} — {self.method} {self.url} ({self.statut})"
