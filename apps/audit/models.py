from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Journal d'audit des actions sensibles (RB-AUD-001 à RB-AUD-003)."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    entite = models.CharField(max_length=100)
    entite_id = models.PositiveIntegerField()
    ancienne_valeur = models.JSONField(null=True, blank=True)
    nouvelle_valeur = models.JSONField(null=True, blank=True)
    horodatage = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "log d'audit"
        verbose_name_plural = "logs d'audit"
        ordering = ["-horodatage"]

    def __str__(self):
        return f"{self.utilisateur} — {self.action} — {self.entite}#{self.entite_id}"


def create_audit_log(utilisateur, action, entite, entite_id, ancienne_valeur=None, nouvelle_valeur=None):
    """Helper pour créer un log d'audit."""
    return AuditLog.objects.create(
        utilisateur=utilisateur,
        action=action,
        entite=entite,
        entite_id=entite_id,
        ancienne_valeur=ancienne_valeur,
        nouvelle_valeur=nouvelle_valeur,
    )
