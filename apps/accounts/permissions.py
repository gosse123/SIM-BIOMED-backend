from rest_framework.permissions import BasePermission
from .models import User


class IsActiveUser(BasePermission):
    """Vérifie que l'utilisateur est authentifié et actif."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active


class IsAdministrateur(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role == User.Role.ADMINISTRATEUR


class IsResponsableBiomedical(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in (
            User.Role.ADMINISTRATEUR,
            User.Role.RESPONSABLE_BIOMEDICAL,
        )


class IsTechnicien(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in (
            User.Role.ADMINISTRATEUR,
            User.Role.RESPONSABLE_BIOMEDICAL,
            User.Role.TECHNICIEN,
        )


class IsPersonnelSoignant(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in (
            User.Role.ADMINISTRATEUR,
            User.Role.RESPONSABLE_BIOMEDICAL,
            User.Role.TECHNICIEN,
            User.Role.PERSONNEL_SOIGNANT,
        )


class IsDirection(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in (
            User.Role.ADMINISTRATEUR,
            User.Role.DIRECTION,
        )


class CanManageUsers(BasePermission):
    """RB-SEC-001 : Seul l'administrateur peut gérer les utilisateurs."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role == User.Role.ADMINISTRATEUR


class CanManageEquipment(BasePermission):
    """RB-SEC-002 : Responsable peut gérer les équipements."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in (
            User.Role.ADMINISTRATEUR,
            User.Role.RESPONSABLE_BIOMEDICAL,
        )


class CanQualifyFailure(BasePermission):
    """RB-SEC-002 : Seul le responsable peut qualifier."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in (
            User.Role.ADMINISTRATEUR,
            User.Role.RESPONSABLE_BIOMEDICAL,
        )


class CanDiagnoseFailure(BasePermission):
    """RB-SEC-003 : Technicien peut diagnostiquer."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in (
            User.Role.ADMINISTRATEUR,
            User.Role.RESPONSABLE_BIOMEDICAL,
            User.Role.TECHNICIEN,
        )


class CanCloseFailure(BasePermission):
    """RB-SEC-002 : Responsable peut clôturer."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in (
            User.Role.ADMINISTRATEUR,
            User.Role.RESPONSABLE_BIOMEDICAL,
        )


class CanReportFailure(BasePermission):
    """RB-SEC-004 : Personnel soignant peut signaler."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in (
            User.Role.ADMINISTRATEUR,
            User.Role.RESPONSABLE_BIOMEDICAL,
            User.Role.TECHNICIEN,
            User.Role.PERSONNEL_SOIGNANT,
        )
