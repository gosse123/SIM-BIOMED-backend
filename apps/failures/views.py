from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.accounts.permissions import CanReportFailure, CanQualifyFailure, CanDiagnoseFailure, CanCloseFailure
from .models import Panne
from .serializers import (
    PanneListSerializer,
    PanneDetailSerializer,
    ReportPanneSerializer,
    QualifyPanneSerializer,
    EvaluateCriticiteSerializer,
    DiagnosePanneSerializer,
    StartInterventionSerializer,
    WaitPieceSerializer,
    WaitPrestataireSerializer,
    StartTestSerializer,
    ClosePanneSerializer,
)


class PanneViewSet(viewsets.ModelViewSet):
    queryset = Panne.objects.select_related("equipement", "signale_par").all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return PanneListSerializer
        if self.action == "report":
            return ReportPanneSerializer
        if self.action == "qualify":
            return QualifyPanneSerializer
        if self.action == "evaluate_criticite":
            return EvaluateCriticiteSerializer
        if self.action == "diagnose":
            return DiagnosePanneSerializer
        if self.action == "start_intervention":
            return StartInterventionSerializer
        if self.action == "wait_piece":
            return WaitPieceSerializer
        if self.action == "wait_prestataire":
            return WaitPrestataireSerializer
        if self.action == "start_test":
            return StartTestSerializer
        if self.action == "close":
            return ClosePanneSerializer
        return PanneDetailSerializer

    def get_permissions(self):
        if self.action == "report":
            return [IsAuthenticated(), CanReportFailure()]
        if self.action == "qualify":
            return [IsAuthenticated(), CanQualifyFailure()]
        if self.action in ("diagnose",):
            return [IsAuthenticated(), CanDiagnoseFailure()]
        if self.action == "close":
            return [IsAuthenticated(), CanCloseFailure()]
        return [IsAuthenticated()]

    def perform_transition(self, request, panne_id, new_statut, serializer_class, **extra_fields):
        try:
            panne = Panne.objects.get(pk=panne_id)
        except Panne.DoesNotExist:
            return Response({"detail": "Panne introuvable."}, status=status.HTTP_404_NOT_FOUND)

        serializer = serializer_class(data=request.data, instance=panne, context={"request": request})
        serializer.is_valid(raise_exception=True)
        panne.statut = new_statut
        for key, val in extra_fields.items():
            setattr(panne, key, val)
        panne.save()
        return Response(PanneDetailSerializer(panne).data)

    @action(detail=True, methods=["post"])
    def report(self, request, pk=None):
        """Signaler une panne — etat SIGNALEE."""
        try:
            panne = Panne.objects.get(pk=pk)
        except Panne.DoesNotExist:
            return Response({"detail": "Panne introuvable."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ReportPanneSerializer(data=request.data, instance=panne, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PanneDetailSerializer(panne).data)

    @action(detail=True, methods=["post"])
    def qualify(self, request, pk=None):
        """Qualifier une panne — SIGNALEE → QUALIFIEE."""
        return self.perform_transition(
            request, pk, Panne.Statut.QUALIFIEE, QualifyPanneSerializer,
            qualifiee_par=request.user,
            date_qualification=timezone.now(),
        )

    @action(detail=True, methods=["post"], url_path="evaluate-criticite")
    def evaluate_criticite(self, request, pk=None):
        """Evaluer la criticite — QUALIFIEE → CRITICITE_EVALUEE."""
        return self.perform_transition(
            request, pk, Panne.Statut.CRITICITE_EVALUEE, EvaluateCriticiteSerializer,
        )

    @action(detail=True, methods=["post"])
    def diagnose(self, request, pk=None):
        """Diagnostiquer — CRITICITE_EVALUEE → EN_DIAGNOSTIC."""
        return self.perform_transition(
            request, pk, Panne.Statut.EN_DIAGNOSTIC, DiagnosePanneSerializer,
            diagnostique_par=request.user,
            date_diagnostic=timezone.now(),
        )

    @action(detail=True, methods=["post"], url_path="start-intervention")
    def start_intervention(self, request, pk=None):
        """Demarrer l'intervention — EN_DIAGNOSTIC → EN_INTERVENTION."""
        return self.perform_transition(
            request, pk, Panne.Statut.EN_INTERVENTION, StartInterventionSerializer,
        )

    @action(detail=True, methods=["post"], url_path="wait-piece")
    def wait_piece(self, request, pk=None):
        """Mettre en attente de piece."""
        return self.perform_transition(
            request, pk, Panne.Statut.EN_ATTENTE_PIECE, WaitPieceSerializer,
        )

    @action(detail=True, methods=["post"], url_path="wait-prestataire")
    def wait_prestataire(self, request, pk=None):
        """Mettre en attente de prestataire."""
        return self.perform_transition(
            request, pk, Panne.Statut.EN_ATTENTE_PRESTATAIRE, WaitPrestataireSerializer,
        )

    @action(detail=True, methods=["post"], url_path="start-test")
    def start_test(self, request, pk=None):
        """Lancer le test — EN_INTERVENTION → EN_TEST."""
        return self.perform_transition(
            request, pk, Panne.Statut.EN_TEST, StartTestSerializer,
        )

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Cloturer — EN_TEST → CLOSE. Test conforme obligatoire (RB-CL-001)."""
        return self.perform_transition(
            request, pk, Panne.Statut.CLOSE, ClosePanneSerializer,
            cloturee_par=request.user,
            date_cloture=timezone.now(),
            commentaire_cloture=request.data.get("commentaire_cloture", ""),
        )
