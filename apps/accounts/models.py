import secrets
import string

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def _generate_temp_password(length=16):
    """Generate a random temporary password with mixed case, digits, and symbols."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    # Guarantee at least one of each category
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&*"),
    ]
    password += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


class Etablissement(models.Model):
    """Établissement hospitalier — MVP : singleton, extensible."""

    nom = models.CharField(max_length=300, unique=True)
    adresse = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "établissement"
        verbose_name_plural = "établissements"

    def __str__(self):
        return self.nom


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
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="utilisateurs",
        verbose_name="Établissement",
    )
    profil_complete = models.BooleanField(
        default=False,
        verbose_name="Profil complété",
        help_text="Indique si l'utilisateur a complété son profil après première connexion.",
    )

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"


class DemandeAcces(models.Model):
    """Demande d'accès soumise par un nouvel utilisateur."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        APPROUVEE = "APPROUVEE", "Approuvée"
        REFUSEE = "REFUSEE", "Refusée"

    nom_complet = models.CharField(max_length=200, verbose_name="Nom complet")
    email = models.EmailField(unique=True, verbose_name="Email professionnel")
    role_souhaite = models.CharField(
        max_length=30,
        choices=[(r, l) for r, l in User.Role.choices if r not in (User.Role.ADMINISTRATEUR, User.Role.RESPONSABLE_BIOMEDICAL)],
        verbose_name="Rôle souhaité",
    )
    justification = models.TextField(verbose_name="Justification de la demande")
    service = models.CharField(max_length=200, blank=True, verbose_name="Service d'affectation")
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
    )
    traite_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demandes_traitees",
        verbose_name="Traité par",
    )
    motif_rejet = models.TextField(blank=True, verbose_name="Motif du rejet")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "demande d'accès"
        verbose_name_plural = "demandes d'accès"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.nom_complet} — {self.get_statut_display()}"

    def approuver(self, admin_user, etablissement=None):
        """Approuve la demande et crée l'utilisateur.

        L'établissement du nouvel utilisateur est celui de l'administrateur
        qui approuve (ou `etablissement` explicitement fourni par un
        super-admin sans établissement). Jamais de choix libre.

        Retourne (user, temp_password) : le mot de passe temporaire ne doit
        être communiqué qu'à l'administrateur (réponse API), jamais persisté."""
        if self.statut != self.Statut.EN_ATTENTE:
            raise ValueError("Cette demande a déjà été traitée.")

        etab = etablissement or admin_user.etablissement

        # Créer l'utilisateur avec un mot de passe temporaire
        username = self.email.split("@")[0]
        # S'assurer que le username est unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            username=username,
            email=self.email,
            first_name=self.nom_complet.split()[0] if self.nom_complet.split() else "",
            last_name=" ".join(self.nom_complet.split()[1:]) if len(self.nom_complet.split()) > 1 else "",
            role=self.role_souhaite,
            etablissement=etab,
            is_active=True,
            profil_complete=False,
        )
        # Mot de passe temporaire aléatoire — l'utilisateur devra le changer
        temp_password = _generate_temp_password()
        user.set_password(temp_password)
        user.save()

        self.statut = self.Statut.APPROUVEE
        self.traite_par = admin_user
        self.date_traitement = timezone.now()
        self.save(update_fields=["statut", "traite_par", "date_traitement"])

        # Créer notification pour l'utilisateur — sans le mot de passe
        # (un identifiant de connexion n'est jamais persisté en clair en base)
        Notification.objects.create(
            destinataire=user,
            titre="Demande d'accès approuvée",
            message=(
                f"Votre demande d'accès a été approuvée.\n"
                f"Identifiant : {username}\n\n"
                f"Votre mot de passe temporaire vous sera communiqué par "
                f"l'administrateur. Vous devez le changer après connexion."
            ),
            lien="/complete-profile",
        )

        return user, temp_password

    def rejeter(self, admin_user, motif=""):
        """Rejette la demande."""
        if self.statut != self.Statut.EN_ATTENTE:
            raise ValueError("Cette demande a déjà été traitée.")

        self.statut = self.Statut.REFUSEE
        self.traite_par = admin_user
        self.motif_rejet = motif
        self.date_traitement = timezone.now()
        self.save(update_fields=["statut", "traite_par", "motif_rejet", "date_traitement"])


class Notification(models.Model):
    """Notification in-app pour un utilisateur."""

    destinataire = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    titre = models.CharField(max_length=200)
    message = models.TextField()
    lu = models.BooleanField(default=False)
    lien = models.CharField(max_length=200, blank=True, verbose_name="Lien de navigation")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.titre} → {self.destinataire.username}"

    def marquer_lue(self):
        self.lu = True
        self.save(update_fields=["lu"])
