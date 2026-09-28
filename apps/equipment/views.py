from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import CanManageEquipment
from apps.accounts.scoping import scope_to_etablissement
from apps.audit.models import create_audit_log

from .models import Equipment, Localisation, Service
from .serializers import (
    EquipmentDetailSerializer,
    EquipmentListSerializer,
    LocalisationSerializer,
    ServiceSerializer,
)


class ServiceViewSet(viewsets.ModelViewSet):
    """CRUD services hospitaliers — cloisonnés par établissement."""

    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated, CanManageEquipment]
    pagination_class = None

    def get_queryset(self):
        return scope_to_etablissement(
            Service.objects.all(), self.request.user, champ="etablissement"
        )

    def perform_create(self, serializer):
        serializer.save(etablissement=self.request.user.etablissement)


class LocalisationViewSet(viewsets.ModelViewSet):
    """CRUD localisations (bâtiment, étage, salle) — cloisonnées par établissement."""

    queryset = Localisation.objects.all()
    serializer_class = LocalisationSerializer
    permission_classes = [IsAuthenticated, CanManageEquipment]
    pagination_class = None

    def get_queryset(self):
        return scope_to_etablissement(
            Localisation.objects.all(), self.request.user, champ="etablissement"
        )

    def perform_create(self, serializer):
        serializer.save(etablissement=self.request.user.etablissement)


class EquipmentViewSet(viewsets.ModelViewSet):
    """CRUD équipements — filtrés par établissement de l'utilisateur (MVP mono-établissement)."""

    permission_classes = [IsAuthenticated, CanManageEquipment]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["num_inventaire", "nom", "num_serie", "marque", "modele"]
    ordering_fields = ["created_at", "nom", "num_inventaire", "etat_operationnel"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Equipment.objects.select_related("service", "localisation").all()
        return scope_to_etablissement(qs, self.request.user, champ="etablissement")

    def get_serializer_class(self):
        if self.action == "list":
            return EquipmentListSerializer
        return EquipmentDetailSerializer

    def perform_create(self, serializer):
        # L'établissement est hérité de l'utilisateur — jamais librement choisi
        equipement = serializer.save(etablissement=self.request.user.etablissement)
        create_audit_log(
            utilisateur=self.request.user,
            action="equipment.create",
            entite="Equipment",
            entite_id=equipement.id,
            nouvelle_valeur={
                "nom": equipement.nom,
                "num_inventaire": equipement.num_inventaire,
                "etat_operationnel": equipement.etat_operationnel,
            },
        )

    def perform_update(self, serializer):
        old_data = {
            "etat_operationnel": serializer.instance.etat_operationnel,
            "niveau_criticite": serializer.instance.niveau_criticite,
        }
        equipement = serializer.save()
        create_audit_log(
            utilisateur=self.request.user,
            action="equipment.update",
            entite="Equipment",
            entite_id=equipement.id,
            ancienne_valeur=old_data,
            nouvelle_valeur={
                "etat_operationnel": equipement.etat_operationnel,
                "niveau_criticite": equipement.niveau_criticite,
            },
        )

    def perform_destroy(self, instance):
        create_audit_log(
            utilisateur=self.request.user,
            action="equipment.delete",
            entite="Equipment",
            entite_id=instance.id,
            ancienne_valeur={
                "nom": instance.nom,
                "num_inventaire": instance.num_inventaire,
            },
        )
        instance.delete()
