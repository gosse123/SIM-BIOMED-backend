from django.db import models
from django.core.exceptions import ValidationError
from apps.accounts.models import User
from apps.equipment.models import Equipment


class MaintenancePlan(models.Model):
    """Plan de maintenance préventive pour un type d'équipement (RB-MP-001)."""

    class Frequence(models.TextChoices):
        HEBDOMADAIRE = "HEBDOMADAIRE", "Hebdomadaire"
        BIMENSUELLE = "BIMENSUELLE", "Bimensuelle"
        MENSUELLE = "MENSUELLE", "Mensuelle"
        TRIMESTRIELLE = "TRIMESTRIELLE", "Trimestrielle"
        SEMESTRIELLE = "SEMESTRIELLE", "Semestrielle"
        ANNUELLE = "ANNUELLE", "Annuelle"

    nom = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    type_equipement = models.CharField(max_length=200, verbose_name="Type d'équipement concerné")
    frequence = models.CharField(max_length=20, choices=Frequence.choices)
    delai_jours = models.PositiveIntegerField(
        verbose_name="Délai entre maintenances (jours)",
        help_text="Nombre de jours entre chaque maintenance préventive",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "plan de maintenance"
        verbose_name_plural = "plans de maintenance"
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.get_frequence_display()})"


class MaintenancePreventive(models.Model):
    """Maintenance préventive planifiée sur un équipement spécifique."""

    class Statut(models.TextChoices):
        PLANIFIEE = "PLANIFIEE", "Planifiée"
        EN_COURS = "EN_COURS", "En cours"
        TERMINEE = "TERMINEE", "Terminée"
        ANNULEE = "ANNULEE", "Annulée"
        EN_RETARD = "EN_RETARD", "En retard"

    plan = models.ForeignKey(MaintenancePlan, on_delete=models.PROTECT, related_name="maintenances")
    equipement = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name="maintenances_preventives")

    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PLANIFIEE)
    date_planifiee = models.DateField()
    date_effective = models.DateField(null=True, blank=True)

    realisee_par = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="maintenances_realisees"
    )
    commentaire = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "maintenance préventive"
        verbose_name_plural = "maintenances préventives"
        ordering = ["date_planifiee"]

    def __str__(self):
        return f"Maintenance {self.plan.nom} — {self.equipement.nom} ({self.date_planifiee})"

    def clean(self):
        if self.date_effective and self.date_planifiee and self.date_effective < self.date_planifiee:
            raise ValidationError("La date effective ne peut pas précéder la date planifiée.")
