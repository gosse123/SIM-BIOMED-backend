from django.db import models
from apps.accounts.models import User
from apps.equipment.models import Equipment
from apps.failures.models import Panne


class Intervention(models.Model):
    """Intervention de maintenance sur un equipement (RB-TEST-001)."""

    class TypeIntervention(models.TextChoices):
        CORRECTIVE = "CORRECTIVE", "Corrective"
        PREVENTIVE = "PREVENTIVE", "Preventive"
        PREDICTIVE = "PREDICTIVE", "Predictive"
        AMELIORATIVE = "AMELIORATIVE", "Ameliorative"

    class StatutIntervention(models.TextChoices):
        PLANIFIEE = "PLANIFIEE", "Planifiee"
        EN_COURS = "EN_COURS", "En cours"
        TERMINEE = "TERMINEE", "Terminee"
        ANNULEE = "ANNULEE", "Annulee"

    panne = models.ForeignKey(
        Panne, on_delete=models.CASCADE, related_name="interventions", null=True, blank=True
    )
    equipement = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="interventions"
    )

    type_intervention = models.CharField(
        max_length=20, choices=TypeIntervention.choices, default=TypeIntervention.CORRECTIVE
    )
    statut = models.CharField(
        max_length=20, choices=StatutIntervention.choices, default=StatutIntervention.PLANIFIEE
    )

    description = models.TextField(verbose_name="Description de l'intervention")
    pieces_utilisees = models.TextField(blank=True, verbose_name="Pièces utilisées")
    temps_passe_minutes = models.PositiveIntegerField(default=0, verbose_name="Temps passé (minutes)")

    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)

    realisee_par = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="interventions_realisees", null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "intervention"
        verbose_name_plural = "interventions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Intervention #{self.id} — {self.equipement.nom} ({self.get_statut_display()})"
