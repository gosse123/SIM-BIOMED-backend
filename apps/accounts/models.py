from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur SIM-BIOMED avec rôles biomédicaux."""

    class Role(models.TextChoices):
        ADMINISTRATEUR = "ADMINISTRATEUR", "Administrateur"
        RESPONSABLE_BIOMEDICAL = "RESPONSABLE_BIOMEDICAL", "Responsable biomédical"
        TECHNICIEN = "TECHNICIEN", "Technicien biomédical"
        PERSONNEL_SOIGNANT = "PERSONNEL_SOIGNANT", "Personnel soignant"
        DIRECTION = "DIRECTION", "Direction"

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.PERSONNEL_SOIGNANT,
    )
    matricule = models.CharField(
        max_length=50, blank=True, verbose_name="Matricule hospitalier"
    )

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
