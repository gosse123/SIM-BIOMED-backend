from django.db.models import Count
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.scoping import scope_to_etablissement
from apps.failures.models import Panne


class WorkQueueView(APIView):
    """
    File de travail : pannes ouvertes priorisées par criticité.
    RB-FIL-001 : Les pannes critiques passent en premier.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        pannes_ouvertes = (
            scope_to_etablissement(Panne.objects.all(), request.user)
            .filter(
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
            .select_related("equipement", "signale_par")
            .order_by(
                # Priorisation par criticite
                "niveau_criticite",  # CRITIQUE < ELEVE < MOYEN < FAIBLE (alphabetical)
                "-created_at",  # Plus récent en premier
            )
        )

        stats = {
            "total_ouvertes": pannes_ouvertes.count(),
            "par_statut": dict(
                pannes_ouvertes.values_list("statut")
                .annotate(count=Count("id"))
                .values_list("statut", "count")
            ),
            "par_criticite": dict(
                pannes_ouvertes.values_list("niveau_criticite")
                .annotate(count=Count("id"))
                .values_list("niveau_criticite", "count")
            ),
            "pannes": [
                {
                    "id": p.id,
                    "equipement_nom": p.equipement.nom,
                    "equipement_num": p.equipement.num_inventaire,
                    "statut": p.statut,
                    "niveau_criticite": p.niveau_criticite,
                    "date_signalement": p.date_signalement.isoformat(),
                    "signale_par_nom": f"{p.signale_par.first_name} {p.signale_par.last_name}",
                    "description_signalement": p.description_signalement[:100],
                }
                for p in pannes_ouvertes
            ],
        }

        return Response(stats)
