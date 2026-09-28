from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.scoping import scope_to_etablissement
from apps.equipment.models import Equipment
from apps.failures.models import Panne
from apps.preventive.models import MaintenancePreventive


class DashboardView(APIView):
    """Dashboard synthétique pour le tableau de bord (RB-DASH-001)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # Compteurs équipements
        equipements = scope_to_etablissement(
            Equipment.objects.all(), request.user, champ="etablissement"
        )
        eq_total = equipements.count()
        eq_fonctionnels = equipements.filter(
            etat_operationnel=Equipment.StatutOperationnel.FONCTIONNEL
        ).count()
        eq_pannees = equipements.filter(
            etat_operationnel=Equipment.StatutOperationnel.EN_PANNE
        ).count()

        # Pannes ouvertes
        pannes_ouvertes = scope_to_etablissement(Panne.objects.all(), request.user).filter(
            statut__in=[
                Panne.Statut.SIGNALEE,
                Panne.Statut.QUALIFIEE,
                Panne.Statut.CRITICITE_EVALUEE,
                Panne.Statut.EN_DIAGNOSTIC,
                Panne.Statut.EN_INTERVENTION,
                Panne.Statut.EN_TEST,
                Panne.Statut.EN_ATTENTE_PIECE,
                Panne.Statut.EN_ATTENTE_PRESTATAIRE,
            ]
        )

        # Pannes des 30 derniers jours
        pannes_30j = (
            scope_to_etablissement(Panne.objects.all(), request.user)
            .filter(date_signalement__gte=thirty_days_ago)
            .count()
        )

        # Maintenances préventives en retard
        maintenances_retard = (
            scope_to_etablissement(MaintenancePreventive.objects.all(), request.user)
            .filter(statut=MaintenancePreventive.Statut.EN_RETARD)
            .count()
        )

        # Maintenances à venir (7 prochains jours)
        in_seven_days = now.date() + timedelta(days=7)
        maintenances_7j = (
            scope_to_etablissement(MaintenancePreventive.objects.all(), request.user)
            .filter(
                statut=MaintenancePreventive.Statut.PLANIFIEE,
                date_planifiee__lte=in_seven_days,
            )
            .count()
        )

        return Response(
            {
                "equipements": {
                    "total": eq_total,
                    "fonctionnels": eq_fonctionnels,
                    "en_panne": eq_pannees,
                },
                "pannes": {
                    "ouvertes": pannes_ouvertes.count(),
                    "par_statut": dict(
                        pannes_ouvertes.values_list("statut")
                        .annotate(count=Count("id"))
                        .values_list("statut", "count")
                    ),
                    "derniers_30_jours": pannes_30j,
                },
                "maintenances": {
                    "en_retard": maintenances_retard,
                    "dans_7_jours": maintenances_7j,
                },
            }
        )
