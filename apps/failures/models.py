from django.core.exceptions import ValidationError
from django.db import models

from apps.accounts.models import User
from apps.equipment.models import Equipment


class Panne(models.Model):
    """Panne biomédicale avec machine à états stricte (RB-03-ETATS-ETATS-PANNE)."""

    class Statut(models.TextChoices):
        SIGNALEE = "SIGNALEE", "Signalee"
        QUALIFIEE = "QUALIFIEE", "Qualifiee"
        CRITICITE_EVALUEE = "CRITICITE_EVALUEE", "Criticite evaluee"
        EN_DIAGNOSTIC = "EN_DIAGNOSTIC", "En diagnostic"
        EN_INTERVENTION = "EN_INTERVENTION", "En intervention"
        EN_TEST = "EN_TEST", "En test"
        EN_ATTENTE_PIECE = "EN_ATTENTE_PIECE", "En attente de piece"
        EN_ATTENTE_PRESTATAIRE = "EN_ATTENTE_PRESTATAIRE", "En attente de prestataire"
        CLOSE = "CLOSE", "Close"

    class CriticitePanne(models.TextChoices):
        CRITIQUE = "CRITIQUE", "Critique"
        ELEVE = "ELEVE", "Eleve"
        MOYEN = "MOYEN", "Moyen"
        FAIBLE = "FAIBLE", "Faible"

    class ResultatTest(models.TextChoices):
        CONFORME = "CONFORME", "Conforme"
        SOUS_SURVEILLANCE = "SOUS_SURVEILLANCE", "Sous surveillance"
        NON_CONFORME = "NON_CONFORME", "Non conforme"
        TOUJOURS_EN_PANNE = "TOUJOURS_EN_PANNE", "Toujours en panne"

    # Transitions valides par statut
    TRANSITIONS_VALIDES = {
        Statut.SIGNALEE: [Statut.QUALIFIEE],
        Statut.QUALIFIEE: [Statut.CLOSE, Statut.CRITICITE_EVALUEE],
        Statut.CRITICITE_EVALUEE: [Statut.EN_DIAGNOSTIC],
        Statut.EN_DIAGNOSTIC: [
            Statut.EN_INTERVENTION,
            Statut.EN_ATTENTE_PIECE,
            Statut.EN_ATTENTE_PRESTATAIRE,
        ],
        Statut.EN_INTERVENTION: [Statut.EN_TEST],
        Statut.EN_TEST: [
            Statut.CLOSE,
            Statut.EN_INTERVENTION,
            Statut.EN_ATTENTE_PIECE,
            Statut.EN_ATTENTE_PRESTATAIRE,
        ],
        Statut.EN_ATTENTE_PIECE: [Statut.EN_INTERVENTION],
        Statut.EN_ATTENTE_PRESTATAIRE: [Statut.EN_INTERVENTION],
        Statut.CLOSE: [],
    }

    # Équipement
    equipement = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name="pannes")

    # Signalement
    date_signalement = models.DateTimeField(auto_now_add=True)
    signale_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name="pannes_signalees")
    description_signalement = models.TextField(verbose_name="Description initiale de la panne")

    # Qualification (RB-PANNE-001 : pas de clôture sans qualification)
    date_qualification = models.DateTimeField(null=True, blank=True)
    qualifiee_par = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="pannes_qualifiees"
    )
    observation_qualification = models.TextField(blank=True)

    # Criterium d'urgence
    critere_urgence = models.TextField(blank=True)

    # Statut
    statut = models.CharField(
        max_length=30,
        choices=Statut.choices,
        default=Statut.SIGNALEE,
    )

    # Criterium d'impact
    critere_impact = models.TextField(blank=True)

    # Criterium de criticite
    critere_criticite = models.TextField(blank=True)
    niveau_criticite = models.CharField(
        max_length=20,
        choices=CriticitePanne.choices,
        default=CriticitePanne.MOYEN,
    )

    # Diagnostic (RB-DIAG-001 : diagnostic obligatoire avant intervention)
    date_diagnostic = models.DateTimeField(null=True, blank=True)
    diagnostique_par = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="pannes_diagnostiquees"
    )
    description_diagnostic = models.TextField(blank=True)
    cause_identifiee = models.TextField(blank=True)

    # Resultat du test final
    resultat_test = models.CharField(
        max_length=30,
        choices=ResultatTest.choices,
        default=ResultatTest.CONFORME,
    )

    # Cloture
    date_cloture = models.DateTimeField(null=True, blank=True)
    cloturee_par = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="pannes_cloturees"
    )
    commentaire_cloture = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "panne"
        verbose_name_plural = "pannes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Panne #{self.id} — {self.equipement.nom} ({self.statut})"

    def clean(self):
        if self.pk:
            old = Panne.objects.get(pk=self.pk)
            if old.statut != self.statut:
                if self.statut not in self.TRANSITIONS_VALIDES.get(old.statut, []):
                    raise ValidationError(
                        f"Transition invalide : {old.statut} → {self.statut}. "
                        "Transitions autorisees : "
                        f"{[t.value for t in self.TRANSITIONS_VALIDES[old.statut]]}"
                    )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
