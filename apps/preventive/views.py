from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.accounts.permissions import CanManageEquipment
from apps.audit.models import create_audit_log
from apps.audit.mixins import AuditedCreateMixin
from apps.accounts.scoping import scope_to_etablissement
from .models import MaintenancePlan, MaintenancePreventive
from .serializers import (
    MaintenancePlanSerializer,
    MaintenancePreventiveListSerializer,
    MaintenancePreventiveDetailSerializer,
    CreateMaintenancePreventiveSerializer,
    FinishMaintenanceSerializer,
)


class MaintenancePlanViewSet(viewsets.ModelViewSet):
    """CRUD plans de maintenance préventive."""
    queryset = MaintenancePlan.objects.all()
    serializer_class = MaintenancePlanSerializer
    permission_classes = [IsAuthenticated, CanManageEquipment]
    pagination_class = None


class MaintenancePreventiveViewSet(AuditedCreateMixin, viewsets.ModelViewSet):
    """Maintenances préventives avec transitions de statut et audit (RB-AUD-001)."""
    queryset = MaintenancePreventive.objects.select_related("plan", "equipement").all()
    permission_classes = [IsAuthenticated, CanManageEquipment]
    audit_create_action = "preventive.create"
    audit_entite = "MaintenancePreventive"
    detail_serializer_class = MaintenancePreventiveDetailSerializer

    def get_queryset(self):
        return scope_to_etablissement(
            MaintenancePreventive.objects.select_related("plan", "equipement").all(),
            self.request.user,
        )

    def get_serializer_class(self):
        if self.action == "list":
            return MaintenancePreventiveListSerializer
        if self.action == "create":
            return CreateMaintenancePreventiveSerializer
        if self.action == "finish":
            return FinishMaintenanceSerializer
        return MaintenancePreventiveDetailSerializer

    def get_audit_nouvelle_valeur(self, mp):
        return {
            "plan": mp.plan_id,
            "equipement": mp.equipement_id,
            "date_planifiee": str(mp.date_planifiee),
        }

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Démarrer — PLANIFIEE → EN_COURS."""
        try:
            mp = scope_to_etablissement(MaintenancePreventive.objects.all(), request.user).get(pk=pk)
        except MaintenancePreventive.DoesNotExist:
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if mp.statut != MaintenancePreventive.Statut.PLANIFIEE:
            return Response(
                {"detail": "Seules les maintenances planifiées peuvent démarrer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ancien_statut = mp.statut
        mp.statut = MaintenancePreventive.Statut.EN_COURS
        mp.save()
        create_audit_log(
            utilisateur=request.user,
            action="preventive.start",
            entite="MaintenancePreventive",
            entite_id=mp.id,
            ancienne_valeur={"statut": ancien_statut},
            nouvelle_valeur={"statut": mp.statut},
        )
        return Response(MaintenancePreventiveDetailSerializer(mp).data)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        """Terminer — EN_COURS → TERMINEE."""
        try:
            mp = scope_to_etablissement(MaintenancePreventive.objects.all(), request.user).get(pk=pk)
        except MaintenancePreventive.DoesNotExist:
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if mp.statut != MaintenancePreventive.Statut.EN_COURS:
            return Response(
                {"detail": "Seules les maintenances en cours peuvent être terminées."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ancien_statut = mp.statut
        mp.statut = MaintenancePreventive.Statut.TERMINEE
        mp.date_effective = timezone.now().date()
        mp.realisee_par = request.user
        mp.commentaire = request.data.get("commentaire", "")
        mp.save()
        create_audit_log(
            utilisateur=request.user,
            action="preventive.finish",
            entite="MaintenancePreventive",
            entite_id=mp.id,
            ancienne_valeur={"statut": ancien_statut},
            nouvelle_valeur={"statut": mp.statut},
        )
        return Response(MaintenancePreventiveDetailSerializer(mp).data)
