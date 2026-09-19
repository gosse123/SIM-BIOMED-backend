from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import CanManageEquipment
from .models import Equipment, Service, Localisation
from .serializers import (
    EquipmentListSerializer,
    EquipmentDetailSerializer,
    ServiceSerializer,
    LocalisationSerializer,
)


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated, CanManageEquipment]
    pagination_class = None


class LocalisationViewSet(viewsets.ModelViewSet):
    queryset = Localisation.objects.all()
    serializer_class = LocalisationSerializer
    permission_classes = [IsAuthenticated, CanManageEquipment]
    pagination_class = None


class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.select_related("service", "localisation").all()
    permission_classes = [IsAuthenticated, CanManageEquipment]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["num_inventaire", "nom", "num_serie", "marque", "modele"]
    ordering_fields = ["created_at", "nom", "num_inventaire", "etat_operationnel"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return EquipmentListSerializer
        return EquipmentDetailSerializer
