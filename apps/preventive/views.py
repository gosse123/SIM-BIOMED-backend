from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.accounts.permissions import CanManageEquipment
from .models import MaintenancePlan, MaintenancePreventive
from .serializers import (
    MaintenancePlanSerializer,
    MaintenancePreventiveListSerializer,
    MaintenancePreventiveDetailSerializer,
    CreateMaintenancePreventiveSerializer,
    FinishMaintenanceSerializer,
)


class MaintenancePlanViewSet(viewsets.ModelViewSet):
    queryset = MaintenancePlan.objects.all()
    serializer_class = MaintenancePlanSerializer
    permission_classes = [IsAuthenticated, CanManageEquipment]
    pagination_class = None


class MaintenancePreventiveViewSet(viewsets.ModelViewSet):
    queryset = MaintenancePreventive.objects.select_related("plan", "equipement").all()
    permission_classes = [IsAuthenticated, CanManageEquipment]

    def get_serializer_class(self):
        if self.action == "list":
            return MaintenancePreventiveListSerializer
        if self.action == "create":
            return CreateMaintenancePreventiveSerializer
        if self.action == "finish":
            return FinishMaintenanceSerializer
        return MaintenancePreventiveDetailSerializer

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        try:
            mp = MaintenancePreventive.objects.get(pk=pk)
        except MaintenancePreventive.DoesNotExist:
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if mp.statut != MaintenancePreventive.Statut.PLANIFIEE:
            return Response({"detail": "Seules les maintenances planifiées peuvent démarrer."}, status=status.HTTP_400_BAD_REQUEST)
        mp.statut = MaintenancePreventive.Statut.EN_COURS
        mp.save()
        return Response(MaintenancePreventiveDetailSerializer(mp).data)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        try:
            mp = MaintenancePreventive.objects.get(pk=pk)
        except MaintenancePreventive.DoesNotExist:
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if mp.statut != MaintenancePreventive.Statut.EN_COURS:
            return Response({"detail": "Seules les maintenances en cours peuvent être terminées."}, status=status.HTTP_400_BAD_REQUEST)
        mp.statut = MaintenancePreventive.Statut.TERMINEE
        mp.date_effective = timezone.now().date()
        mp.realisee_par = request.user
        mp.commentaire = request.data.get("commentaire", "")
        mp.save()
        return Response(MaintenancePreventiveDetailSerializer(mp).data)
