from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.accounts.permissions import CanManageEquipment
from .models import Intervention
from .serializers import (
    InterventionListSerializer,
    InterventionDetailSerializer,
    CreateInterventionSerializer,
    StartInterventionSerializer,
    FinishInterventionSerializer,
)


class InterventionViewSet(viewsets.ModelViewSet):
    queryset = Intervention.objects.select_related("equipement", "panne", "realisee_par").all()
    permission_classes = [IsAuthenticated, CanManageEquipment]

    def get_serializer_class(self):
        if self.action == "list":
            return InterventionListSerializer
        if self.action == "create":
            return CreateInterventionSerializer
        if self.action == "start":
            return StartInterventionSerializer
        if self.action == "finish":
            return FinishInterventionSerializer
        return InterventionDetailSerializer

    def perform_create(self, serializer):
        serializer.save(realisee_par=self.request.user)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Demarrer une intervention."""
        try:
            intervention = Intervention.objects.get(pk=pk)
        except Intervention.DoesNotExist:
            return Response({"detail": "Intervention introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if intervention.statut != Intervention.StatutIntervention.PLANIFIEE:
            return Response({"detail": "Seules les interventions planifiees peuvent etre demarrees."}, status=status.HTTP_400_BAD_REQUEST)

        intervention.statut = Intervention.StatutIntervention.EN_COURS
        intervention.date_debut = timezone.now()
        intervention.save()
        return Response(InterventionDetailSerializer(intervention).data)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        """Terminer une intervention."""
        try:
            intervention = Intervention.objects.get(pk=pk)
        except Intervention.DoesNotExist:
            return Response({"detail": "Intervention introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if intervention.statut != Intervention.StatutIntervention.EN_COURS:
            return Response({"detail": "Seules les interventions en cours peuvent etre terminees."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = FinishInterventionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        intervention.statut = Intervention.StatutIntervention.TERMINEE
        intervention.date_fin = timezone.now()
        intervention.temps_passe_minutes = serializer.validated_data.get("temps_passe_minutes", 0)
        intervention.pieces_utilisees = serializer.validated_data.get("pieces_utilisees", "")
        intervention.save()
        return Response(InterventionDetailSerializer(intervention).data)
