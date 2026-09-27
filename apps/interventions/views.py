from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.accounts.permissions import CanManageEquipment
from apps.audit.models import create_audit_log
from apps.audit.mixins import AuditedCreateMixin
from apps.accounts.scoping import scope_to_etablissement
from .models import Intervention
from .serializers import (
    InterventionListSerializer,
    InterventionDetailSerializer,
    CreateInterventionSerializer,
    StartInterventionSerializer,
    FinishInterventionSerializer,
)


class InterventionViewSet(AuditedCreateMixin, viewsets.ModelViewSet):
    """CRUD interventions avec transitions de statut et audit (RB-AUD-001)."""
    queryset = Intervention.objects.select_related("equipement", "panne", "realisee_par").all()
    permission_classes = [IsAuthenticated, CanManageEquipment]
    audit_create_action = "intervention.create"
    audit_entite = "Intervention"
    detail_serializer_class = InterventionDetailSerializer

    def get_queryset(self):
        # File d'interventions priorisée (RB-PR-004) : criticité de la panne
        # liée d'abord (CRITIQUE en tête, alphabétique), puis plus récentes.
        from django.db.models import F
        return scope_to_etablissement(
            Intervention.objects.select_related("equipement", "panne", "realisee_par")
            .order_by(F("panne__niveau_criticite").asc(nulls_last=True), "-created_at"),
            self.request.user,
        )

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
        # Champ métier hors modèle : hors-service total à la prise en charge
        hors_service_total = serializer.validated_data.pop("hors_service_total", False)
        intervention = serializer.save(realisee_par=self.request.user)
        if hors_service_total:
            equipement = intervention.equipement
            ancien_etat = equipement.etat_operationnel
            equipement.etat_operationnel = equipement.StatutOperationnel.HORS_SERVICE
            equipement.save(update_fields=["etat_operationnel"])
            create_audit_log(
                utilisateur=self.request.user,
                action="equipment.hors_service",
                entite="Equipment",
                entite_id=equipement.id,
                ancienne_valeur={"etat_operationnel": ancien_etat},
                nouvelle_valeur={"etat_operationnel": equipement.etat_operationnel,
                                 "intervention_id": intervention.id},
            )

    def get_audit_nouvelle_valeur(self, intervention):
        return {
            "equipement": intervention.equipement_id,
            "type_intervention": intervention.type_intervention,
            "description": intervention.description,
        }

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Démarrer une intervention — PLANIFIEE → EN_COURS."""
        try:
            intervention = scope_to_etablissement(Intervention.objects.all(), request.user).get(pk=pk)
        except Intervention.DoesNotExist:
            return Response({"detail": "Intervention introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if intervention.statut != Intervention.StatutIntervention.PLANIFIEE:
            return Response(
                {"detail": "Seules les interventions planifiées peuvent être démarrées."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ancien_statut = intervention.statut
        intervention.statut = Intervention.StatutIntervention.EN_COURS
        intervention.date_debut = timezone.now()
        intervention.save()
        create_audit_log(
            utilisateur=request.user,
            action="intervention.start",
            entite="Intervention",
            entite_id=intervention.id,
            ancienne_valeur={"statut": ancien_statut},
            nouvelle_valeur={"statut": intervention.statut},
        )
        return Response(InterventionDetailSerializer(intervention).data)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        """Terminer une intervention — EN_COURS → TERMINEE."""
        try:
            intervention = scope_to_etablissement(Intervention.objects.all(), request.user).get(pk=pk)
        except Intervention.DoesNotExist:
            return Response({"detail": "Intervention introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if intervention.statut != Intervention.StatutIntervention.EN_COURS:
            return Response(
                {"detail": "Seules les interventions en cours peuvent être terminées."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = FinishInterventionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        repare_totalement = serializer.validated_data.get("repare_totalement", False)

        ancien_statut = intervention.statut
        intervention.statut = Intervention.StatutIntervention.TERMINEE
        intervention.date_fin = timezone.now()
        intervention.temps_passe_minutes = serializer.validated_data.get("temps_passe_minutes", 0)
        intervention.pieces_utilisees = serializer.validated_data.get("pieces_utilisees", "")
        intervention.save()
        create_audit_log(
            utilisateur=request.user,
            action="intervention.finish",
            entite="Intervention",
            entite_id=intervention.id,
            ancienne_valeur={"statut": ancien_statut},
            nouvelle_valeur={"statut": intervention.statut},
        )

        # RB-CL-002 : réparation totale → remise FONCTIONNEL de l'équipement.
        # La panne liée n'est PAS clôturée ici : elle exige un test (RB-CL-001).
        if repare_totalement:
            equipement = intervention.equipement
            ancien_etat = equipement.etat_operationnel
            equipement.etat_operationnel = equipement.StatutOperationnel.FONCTIONNEL
            equipement.save(update_fields=["etat_operationnel"])
            create_audit_log(
                utilisateur=request.user,
                action="equipment.remise_en_service",
                entite="Equipment",
                entite_id=equipement.id,
                ancienne_valeur={"etat_operationnel": ancien_etat},
                nouvelle_valeur={"etat_operationnel": equipement.etat_operationnel,
                                 "intervention_id": intervention.id},
            )

        return Response(InterventionDetailSerializer(intervention).data)
