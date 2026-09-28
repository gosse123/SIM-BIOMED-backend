from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import (
    CanCloseFailure,
    CanDiagnoseFailure,
    CanEvaluateCriticite,
    CanManageIntervention,
    CanManageWaitState,
    CanQualifyFailure,
    CanReportFailure,
    CanStartIntervention,
    CanStartTest,
)
from apps.accounts.scoping import scope_to_etablissement
from apps.audit.models import create_audit_log
from apps.equipment.status import synchroniser_statut
from domain.failure.transitions import TransitionInvalideError, verifier_transition

from .models import Panne
from .serializers import (
    ClosePanneSerializer,
    DiagnosePanneSerializer,
    EvaluateCriticiteSerializer,
    PanneDetailSerializer,
    PanneListSerializer,
    QualifyPanneSerializer,
    ReportPanneSerializer,
    StartInterventionSerializer,
    StartTestSerializer,
    WaitPieceSerializer,
    WaitPrestataireSerializer,
)


class PanneViewSet(viewsets.ModelViewSet):
    """Gestion du cycle de vie des pannes (RB-SEC-002 à RB-SEC-008)."""

    queryset = Panne.objects.select_related("equipement", "signale_par").all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        # Cloisonnement : seules les pannes de l'établissement de l'utilisateur
        return scope_to_etablissement(
            Panne.objects.select_related("equipement", "signale_par").all(),
            self.request.user,
        )

    def get_serializer_class(self):
        if self.action == "list":
            return PanneListSerializer
        if self.action == "create":
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
        if self.action == "create":
            return [IsAuthenticated(), CanReportFailure()]
        if self.action == "qualify":
            return [IsAuthenticated(), CanQualifyFailure()]
        if self.action == "evaluate_criticite":
            return [IsAuthenticated(), CanEvaluateCriticite()]
        if self.action == "diagnose":
            return [IsAuthenticated(), CanDiagnoseFailure()]
        if self.action == "start_intervention":
            return [IsAuthenticated(), CanStartIntervention()]
        if self.action in ("wait_piece", "wait_prestataire"):
            return [IsAuthenticated(), CanManageWaitState()]
        if self.action == "start_test":
            return [IsAuthenticated(), CanStartTest()]
        if self.action == "close":
            return [IsAuthenticated(), CanCloseFailure()]
        if self.action == "affecter":
            return [IsAuthenticated(), CanManageIntervention()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Signaler une panne — état initial SIGNALEE."""
        serializer = ReportPanneSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        panne = serializer.save()
        create_audit_log(
            utilisateur=request.user,
            action="panne.report",
            entite="Panne",
            entite_id=panne.id,
            nouvelle_valeur={
                "equipement": panne.equipement_id,
                "description": panne.description_signalement,
                "statut": panne.statut,
            },
        )
        # RB-CL-002 : équipement fonctionnel signalé en panne → EN_PANNE.
        synchroniser_statut(
            panne.equipement,
            "EN_PANNE",
            request.user,
            f"Panne #{panne.id} signalée",
        )
        return Response(PanneDetailSerializer(panne).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        """Mise à jour classique avec trace d'audit (RB-AUD-001)."""
        ancienne = {k: str(v) for k, v in serializer.validated_data.items()}
        panne = serializer.save()
        create_audit_log(
            utilisateur=self.request.user,
            action="panne.update",
            entite="Panne",
            entite_id=panne.id,
            ancienne_valeur=ancienne,
            nouvelle_valeur={k: str(getattr(panne, k)) for k in ancienne},
        )

    @staticmethod
    def _synchroniser_equipement(request, panne, new_statut):
        """Le statut opérationnel suit le cycle de vie de la panne."""
        cible = {
            Panne.Statut.EN_INTERVENTION: "EN_MAINTENANCE",
            Panne.Statut.EN_ATTENTE_PIECE: "EN_ATTENTE_PIECE_OU_PRESTATAIRE",
            Panne.Statut.EN_ATTENTE_PRESTATAIRE: "EN_ATTENTE_PIECE_OU_PRESTATAIRE",
        }.get(new_statut)
        if cible is None and new_statut == Panne.Statut.CLOSE:
            cible = (
                "FONCTIONNEL"
                if panne.resultat_test == Panne.ResultatTest.CONFORME
                else "FONCTIONNEL_SOUS_SURVEILLANCE"
            )
        if cible:
            synchroniser_statut(
                panne.equipement,
                cible,
                request.user,
                f"Panne #{panne.id} → {new_statut}",
            )

    def perform_transition(
        self, request, panne_id, new_statut, serializer_class, audit_action, **extra_fields
    ):
        """Exécuter une transition de statut avec audit."""
        try:
            # Cloisonnement appliqué aussi aux actions sur un objet précis
            panne = scope_to_etablissement(Panne.objects.all(), request.user).get(pk=panne_id)
        except Panne.DoesNotExist:
            return Response({"detail": "Panne introuvable."}, status=status.HTTP_404_NOT_FOUND)

        ancien_statut = panne.statut
        # Règle métier RB-004 : la transition est validée par la couche domaine
        try:
            verifier_transition(ancien_statut, new_statut)
        except TransitionInvalideError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = serializer_class(
            data=request.data, instance=panne, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        panne.statut = new_statut
        for key, val in serializer.validated_data.items():
            setattr(panne, key, val)
        for key, val in extra_fields.items():
            setattr(panne, key, val)
        try:
            panne.save()
        except DjangoValidationError as e:
            return Response(
                {"detail": e.message if hasattr(e, "message") else str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        create_audit_log(
            utilisateur=request.user,
            action=audit_action,
            entite="Panne",
            entite_id=panne.id,
            ancienne_valeur={"statut": ancien_statut},
            nouvelle_valeur={"statut": panne.statut},
        )
        self._synchroniser_equipement(request, panne, panne.statut)
        return Response(PanneDetailSerializer(panne).data)

    @action(detail=True, methods=["post"], url_path="evaluate-criticite")
    def evaluate_criticite(self, request, pk=None):
        """Évaluer la criticité — QUALIFIEE → CRITICITE_EVALUEE."""
        return self.perform_transition(
            request,
            pk,
            Panne.Statut.CRITICITE_EVALUEE,
            EvaluateCriticiteSerializer,
            audit_action="panne.evaluate_criticite",
        )

    @action(detail=True, methods=["post"])
    def qualify(self, request, pk=None):
        """Qualifier une panne — SIGNALEE → QUALIFIEE."""
        return self.perform_transition(
            request,
            pk,
            Panne.Statut.QUALIFIEE,
            QualifyPanneSerializer,
            audit_action="panne.qualify",
            qualifiee_par=request.user,
            date_qualification=timezone.now(),
        )

    @action(detail=True, methods=["post"])
    def diagnose(self, request, pk=None):
        """Diagnostiquer — CRITICITE_EVALUEE → EN_DIAGNOSTIC."""
        return self.perform_transition(
            request,
            pk,
            Panne.Statut.EN_DIAGNOSTIC,
            DiagnosePanneSerializer,
            audit_action="panne.diagnose",
            diagnostique_par=request.user,
            date_diagnostic=timezone.now(),
        )

    @action(detail=True, methods=["post"], url_path="start-intervention")
    def start_intervention(self, request, pk=None):
        """Démarrer l'intervention — EN_DIAGNOSTIC → EN_INTERVENTION."""
        return self.perform_transition(
            request,
            pk,
            Panne.Statut.EN_INTERVENTION,
            StartInterventionSerializer,
            audit_action="panne.start_intervention",
        )

    @action(detail=True, methods=["post"], url_path="wait-piece")
    def wait_piece(self, request, pk=None):
        """Mettre en attente de pièce."""
        return self.perform_transition(
            request,
            pk,
            Panne.Statut.EN_ATTENTE_PIECE,
            WaitPieceSerializer,
            audit_action="panne.wait_piece",
        )

    @action(detail=True, methods=["post"], url_path="wait-prestataire")
    def wait_prestataire(self, request, pk=None):
        """Mettre en attente de prestataire."""
        return self.perform_transition(
            request,
            pk,
            Panne.Statut.EN_ATTENTE_PRESTATAIRE,
            WaitPrestataireSerializer,
            audit_action="panne.wait_prestataire",
        )

    @action(detail=True, methods=["post"], url_path="start-test")
    def start_test(self, request, pk=None):
        """Lancer le test — EN_INTERVENTION → EN_TEST."""
        return self.perform_transition(
            request,
            pk,
            Panne.Statut.EN_TEST,
            StartTestSerializer,
            audit_action="panne.start_test",
        )

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Clôturer — EN_TEST → CLOSE. Test conforme obligatoire (RB-CL-001)."""
        return self.perform_transition(
            request,
            pk,
            Panne.Statut.CLOSE,
            ClosePanneSerializer,
            audit_action="panne.close",
            cloturee_par=request.user,
            date_cloture=timezone.now(),
            commentaire_cloture=request.data.get("commentaire_cloture", ""),
        )

    @action(detail=True, methods=["post"], url_path="affecter")
    def affecter(self, request, pk=None):
        """Affecter la panne à un technicien (prise en charge — RB-PR-004).

        Corps vide : prise en charge par l'utilisateur courant.
        {"utilisateur": null} : désaffecter.
        {"utilisateur": <id>} : affecter à un pair.
        """
        try:
            panne = scope_to_etablissement(
                Panne.objects.select_related("equipement", "affecte_a"), request.user
            ).get(pk=pk)
        except Panne.DoesNotExist:
            return Response({"detail": "Panne introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if "utilisateur" in request.data and request.data["utilisateur"] in (None, "", "null"):
            cible = None
        elif "utilisateur" not in request.data:
            cible = request.user
        else:
            try:
                cible = User.objects.get(pk=request.data["utilisateur"])
            except (User.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"detail": "Utilisateur introuvable."}, status=status.HTTP_400_BAD_REQUEST
                )
            if (
                request.user.etablissement_id
                and cible.etablissement_id != request.user.etablissement_id
            ):
                return Response(
                    {"detail": "Cet utilisateur n'appartient pas à votre établissement."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if cible.role not in (
                User.Role.TECHNICIEN,
                User.Role.RESPONSABLE_BIOMEDICAL,
                User.Role.ADMINISTRATEUR,
            ):
                return Response(
                    {"detail": "Seuls les techniciens et responsables peuvent être affectés."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        ancien = panne.affecte_a_id
        panne.affecte_a = cible
        panne.save(update_fields=["affecte_a", "updated_at"])
        create_audit_log(
            utilisateur=request.user,
            action="panne.affecter",
            entite="Panne",
            entite_id=panne.id,
            ancienne_valeur={"affecte_a": ancien},
            nouvelle_valeur={"affecte_a": panne.affecte_a_id},
        )
        return Response(PanneDetailSerializer(panne).data)
