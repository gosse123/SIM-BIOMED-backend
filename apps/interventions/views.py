from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import CanManageEquipment, CanManageIntervention
from apps.accounts.scoping import scope_to_etablissement
from apps.audit.mixins import AuditedCreateMixin
from apps.audit.models import create_audit_log
from apps.equipment.status import synchroniser_statut
from domain.interventions.transitions import (
    TransitionInterventionInvalideError,
    verifier_transition,
)

from .models import Intervention
from .serializers import (
    CreateInterventionSerializer,
    FinishInterventionSerializer,
    InterventionDetailSerializer,
    InterventionListSerializer,
    StartInterventionSerializer,
)

# Ordre de criticité de la file (RB-PR-004) — pas de tri alphabétique.
CRITICITE_ORDRE = Case(
    When(panne__niveau_criticite="CRITIQUE", then=Value(0)),
    When(panne__niveau_criticite="ELEVE", then=Value(1)),
    When(panne__niveau_criticite="MOYEN", then=Value(2)),
    When(panne__niveau_criticite="FAIBLE", then=Value(3)),
    default=Value(9),
    output_field=IntegerField(),
)


class InterventionViewSet(AuditedCreateMixin, viewsets.ModelViewSet):
    """CRUD interventions avec transitions de statut et audit (RB-AUD-001)."""

    queryset = Intervention.objects.select_related("equipement", "panne", "realisee_par").all()
    permission_classes = [IsAuthenticated, CanManageIntervention]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    audit_create_action = "intervention.create"
    audit_entite = "Intervention"
    detail_serializer_class = InterventionDetailSerializer

    def get_permissions(self):
        # RB-SEC-003 : exécution par technicien/responsable ; suppression
        # réservée à la gestion (administrateur/responsable).
        if self.action == "destroy":
            return [IsAuthenticated(), CanManageEquipment()]
        return [IsAuthenticated(), CanManageIntervention()]

    def get_queryset(self):
        # Cloisonnement multi-établissements + file priorisée (RB-PR-004) :
        # criticité de la panne liée d'abord (CRITIQUE en tête), puis plus
        # récentes. Filtres serveur : ?statut, ?type, ?equipement.
        qs = scope_to_etablissement(
            Intervention.objects.select_related("equipement", "panne", "realisee_par"),
            self.request.user,
        )
        statut = self.request.query_params.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        type_intervention = self.request.query_params.get("type")
        if type_intervention:
            qs = qs.filter(type_intervention=type_intervention)
        equipement = self.request.query_params.get("equipement")
        if equipement:
            qs = qs.filter(equipement_id=equipement)
        return qs.order_by(CRITICITE_ORDRE, "-created_at")

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
                nouvelle_valeur={
                    "etat_operationnel": equipement.etat_operationnel,
                    "intervention_id": intervention.id,
                },
            )

    def perform_update(self, serializer):
        """Mise à jour (description, pièces, temps) avec trace d'audit."""
        ancienne = {k: str(v) for k, v in serializer.validated_data.items()}
        intervention = serializer.save()
        create_audit_log(
            utilisateur=self.request.user,
            action="intervention.update",
            entite="Intervention",
            entite_id=intervention.id,
            ancienne_valeur=ancienne,
            nouvelle_valeur={k: str(getattr(intervention, k)) for k in ancienne},
        )

    def perform_destroy(self, instance):
        create_audit_log(
            utilisateur=self.request.user,
            action="intervention.delete",
            entite="Intervention",
            entite_id=instance.id,
            ancienne_valeur={
                "equipement": instance.equipement_id,
                "type_intervention": instance.type_intervention,
                "statut": instance.statut,
                "description": instance.description,
            },
        )
        instance.delete()

    def get_audit_nouvelle_valeur(self, intervention):
        return {
            "equipement": intervention.equipement_id,
            "type_intervention": intervention.type_intervention,
            "description": intervention.description,
        }

    def _get_intervention(self, request, pk):
        try:
            return scope_to_etablissement(Intervention.objects.all(), request.user).get(pk=pk)
        except Intervention.DoesNotExist:
            return None

    def _verifier_ou_rejeter(self, intervention, nouveau_statut):
        """Contrôle par la couche domaine (RB-004) — réponse DRF ou None."""
        try:
            verifier_transition(intervention.statut, nouveau_statut)
        except TransitionInterventionInvalideError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return None

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Démarrer une intervention — PLANIFIEE → EN_COURS (RB-IN-001)."""
        intervention = self._get_intervention(request, pk)
        if intervention is None:
            return Response(
                {"detail": "Intervention introuvable."}, status=status.HTTP_404_NOT_FOUND
            )
        erreur = self._verifier_ou_rejeter(
            intervention, Intervention.StatutIntervention.EN_COURS
        )
        if erreur:
            return erreur

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
        # Statut opérationnel : l'équipement passe en maintenance (RB-CL-002).
        synchroniser_statut(
            intervention.equipement,
            "EN_MAINTENANCE",
            request.user,
            f"Intervention #{intervention.id} démarrée",
        )
        return Response(InterventionDetailSerializer(intervention).data)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        """Terminer une intervention — EN_COURS → TERMINEE (RB-IN-001)."""
        intervention = self._get_intervention(request, pk)
        if intervention is None:
            return Response(
                {"detail": "Intervention introuvable."}, status=status.HTTP_404_NOT_FOUND
            )
        erreur = self._verifier_ou_rejeter(
            intervention, Intervention.StatutIntervention.TERMINEE
        )
        if erreur:
            return erreur

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
                nouvelle_valeur={
                    "etat_operationnel": equipement.etat_operationnel,
                    "intervention_id": intervention.id,
                },
            )
        elif intervention.panne_id:
            # Réparation partielle : retour en panne jusqu'au test (RB-CL-001).
            synchroniser_statut(
                intervention.equipement,
                "EN_PANNE",
                request.user,
                f"Intervention #{intervention.id} terminée sans réparation totale",
            )

        return Response(InterventionDetailSerializer(intervention).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Annuler — PLANIFIEE/EN_COURS → ANNULEE (RB-004)."""
        intervention = self._get_intervention(request, pk)
        if intervention is None:
            return Response(
                {"detail": "Intervention introuvable."}, status=status.HTTP_404_NOT_FOUND
            )
        erreur = self._verifier_ou_rejeter(
            intervention, Intervention.StatutIntervention.ANNULEE
        )
        if erreur:
            return erreur

        ancien_statut = intervention.statut
        intervention.statut = Intervention.StatutIntervention.ANNULEE
        intervention.save(update_fields=["statut", "updated_at"])
        create_audit_log(
            utilisateur=request.user,
            action="intervention.cancel",
            entite="Intervention",
            entite_id=intervention.id,
            ancienne_valeur={"statut": ancien_statut},
            nouvelle_valeur={"statut": intervention.statut},
        )
        # Intervention déjà commencée sur une panne → retour en panne.
        if ancien_statut == Intervention.StatutIntervention.EN_COURS and intervention.panne_id:
            synchroniser_statut(
                intervention.equipement,
                "EN_PANNE",
                request.user,
                f"Intervention #{intervention.id} annulée",
            )
        return Response(InterventionDetailSerializer(intervention).data)
