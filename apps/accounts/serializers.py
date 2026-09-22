from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User, Etablissement, DemandeAcces, Notification


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Identifiants incorrects.")
        if not user.is_active:
            raise serializers.ValidationError("Compte désactivé.")
        data["user"] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    etablissement_nom = serializers.CharField(source="etablissement.nom", read_only=True, default=None)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "role", "matricule", "is_active", "etablissement", "etablissement_nom", "profil_complete")
        read_only_fields = ("id",)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "first_name", "last_name", "role", "matricule", "etablissement")
        read_only_fields = ("id",)

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "matricule", "is_active")
        read_only_fields = ("id",)


class SetRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)

    def validate_role(self, value):
        if value in (User.Role.ADMINISTRATEUR,):
            # Seul un admin peut promouvoir en admin
            request = self.context.get("request")
            if request and request.user.role != User.Role.ADMINISTRATEUR:
                raise serializers.ValidationError("Seul un administrateur peut attribuer ce rôle.")
        return value


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name", "role", "matricule")

    def validate_role(self, value):
        # MVP : les rôles admin ne sont pas autorisés à l'auto-inscription
        if value in (User.Role.ADMINISTRATEUR, User.Role.RESPONSABLE_BIOMEDICAL):
            raise serializers.ValidationError("Rôle non autorisé à l'auto-inscription.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return value


class EtablissementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Etablissement
        fields = ("id", "nom", "adresse", "actif")
        read_only_fields = ("id",)


# --- Demande d'accès ---

class DemandeAccesCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la soumission d'une demande (public)."""

    class Meta:
        model = DemandeAcces
        fields = ("id", "nom_complet", "email", "role_souhaite", "justification", "service")
        read_only_fields = ("id",)

    def validate_email(self, value):
        if DemandeAcces.objects.filter(email=value, statut=DemandeAcces.Statut.EN_ATTENTE).exists():
            raise serializers.ValidationError("Une demande en attente existe déjà pour cet email.")
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet email.")
        return value


class DemandeAccesSerializer(serializers.ModelSerializer):
    """Serializer pour l'admin (lecture)."""
    traite_par_username = serializers.CharField(source="traite_par.username", read_only=True, default=None)

    class Meta:
        model = DemandeAcces
        fields = ("id", "nom_complet", "email", "role_souhaite", "justification", "service",
                  "statut", "traite_par", "traite_par_username", "motif_rejet", "date_creation", "date_traitement")
        read_only_fields = ("id", "date_creation", "date_traitement")


class RejectDemandeSerializer(serializers.Serializer):
    motif = serializers.CharField(required=False, allow_blank=True)


# --- Notification ---

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "titre", "message", "lu", "lien", "date_creation")
        read_only_fields = ("id", "date_creation")


# --- Complétion profil ---

class CompleteProfileSerializer(serializers.Serializer):
    matricule = serializers.CharField(max_length=50)
    service = serializers.CharField(max_length=200, required=False, allow_blank=True)
    etablissement = serializers.PrimaryKeyRelatedField(queryset=Etablissement.objects.filter(actif=True))
    new_password = serializers.CharField(min_length=8, write_only=True)

    def validate_matricule(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le matricule est obligatoire.")
        return value.strip()

    def validate_new_password(self, value):
        if value.lower() in ("changeme123!", "changeme123"):
            raise serializers.ValidationError("Ce mot de passe est trop simple. Choisissez un mot de passe fort.")
        return value
