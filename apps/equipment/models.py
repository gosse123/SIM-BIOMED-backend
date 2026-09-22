from django.db import models


class Service(models.Model):
    """Service hospitalier (RB-EQ-002)."""
    nom = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    etablissement = models.ForeignKey(
        "accounts.Etablissement",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="services",
        verbose_name="Établissement",
    )

    class Meta:
        verbose_name = "service"
        verbose_name_plural = "services"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Localisation(models.Model):
    """Localisation physique de l'équipement (RB-EQ-002)."""
    batiment = models.CharField(max_length=200)
    etage = models.CharField(max_length=50, blank=True)
    salle = models.CharField(max_length=100)
    etablissement = models.ForeignKey(
        "accounts.Etablissement",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="localisations",
        verbose_name="Établissement",
    )

    class Meta:
        verbose_name = "localisation"
        verbose_name_plural = "localisations"
        ordering = ["batiment", "etage", "salle"]

    def __str__(self):
        parts = [self.batiment]
        if self.etage:
            parts.append(f"Étage {self.etage}")
        parts.append(self.salle)
        return " - ".join(parts)


class Equipment(models.Model):
    """Équipement biomédical (RB-EQ-001, RB-EQ-002, RB-EQ-003)."""

    class StatutOperationnel(models.TextChoices):
        FONCTIONNEL = "FONCTIONNEL", "Fonctionnel"
        FONCTIONNEL_SOUS_SURVEILLANCE = "FONCTIONNEL_SOUS_SURVEILLANCE", "Fonctionnel sous surveillance"
        EN_PANNE = "EN_PANNE", "En panne"
        EN_MAINTENANCE = "EN_MAINTENANCE", "En maintenance"
        EN_ATTENTE_PIECE_OU_PRESTATAIRE = "EN_ATTENTE_PIECE_OU_PRESTATAIRE", "En attente de pièce ou prestataire"
        HORS_SERVICE = "HORS_SERVICE", "Hors service"
        REFORME = "REFORME", "Réformé"

    class Criticite(models.TextChoices):
        CRITIQUE = "CRITIQUE", "Critique"
        ELEVE = "ELEVE", "Élevé"
        MOYEN = "MOYEN", "Moyen"
        FAIBLE = "FAIBLE", "Faible"

    class CycleVie(models.TextChoices):
        RECEPTION = "RECEPTION", "Réception"
        INSTALLATION = "INSTALLATION", "Installation"
        MISE_EN_SERVICE = "MISE_EN_SERVICE", "Mise en service"
        EXPLOITATION = "EXPLOITATION", "Exploitation"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        REFORME = "REFORME", "Réformé"

    # RB-EQ-001 : Identifiant unique
    num_inventaire = models.CharField(max_length=50, unique=True, verbose_name="Numéro d'inventaire")

    # RB-EQ-002 : Identification
    nom = models.CharField(max_length=300)
    type_equipement = models.CharField(max_length=200, verbose_name="Type d'équipement")
    categorie = models.CharField(max_length=200)
    marque = models.CharField(max_length=200)
    modele = models.CharField(max_length=200)
    num_serie = models.CharField(max_length=200, verbose_name="Numéro de série")

    # Relations
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="equipements")
    localisation = models.ForeignKey(Localisation, on_delete=models.PROTECT, related_name="equipements")
    etablissement = models.ForeignKey(
        "accounts.Etablissement",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipements",
        verbose_name="Établissement",
    )

    # Dates
    date_reception = models.DateField(null=True, blank=True)
    date_installation = models.DateField(null=True, blank=True)
    date_mise_service = models.DateField(null=True, blank=True)

    # RB-EQ-003 : Statut opérationnel
    etat_operationnel = models.CharField(
        max_length=40,
        choices=StatutOperationnel.choices,
        default=StatutOperationnel.FONCTIONNEL,
    )

    # Criticité
    niveau_criticite = models.CharField(
        max_length=20,
        choices=Criticite.choices,
        default=Criticite.MOYEN,
    )

    # Cycle de vie
    statut_cycle_vie = models.CharField(
        max_length=20,
        choices=CycleVie.choices,
        default=CycleVie.EXPLOITATION,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "équipement"
        verbose_name_plural = "équipements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nom} ({self.num_inventaire})"
