from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Avg, Count, F, ExpressionWrapper, DurationField
from apps.equipment.models import Equipment
from apps.failures.models import Panne
from apps.accounts.scoping import scope_to_etablissement


class IndicateursView(APIView):
    """
    Indicateurs MTBF et MTTR par équipement (RB-IND-001, RB-IND-002).
    MTBF = Mean Time Between Failures = jours entre pannes consécutives
    MTTR = Mean Time To Repair = temps moyen de résolution
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        equipements = scope_to_etablissement(Equipment.objects.all(), request.user, champ="etablissement").filter(
            etat_operationnel__in=[
                Equipment.StatutOperationnel.FONCTIONNEL,
                Equipment.StatutOperationnel.FONCTIONNEL_SOUS_SURVEILLANCE,
            ]
        )

        resultats = []
        for eq in equipements:
            pannes = Panne.objects.filter(equipement=eq, statut=Panne.Statut.CLOSE).order_by("date_cloture")

            if pannes.count() < 1:
                resultats.append({
                    "equipement_id": eq.id,
                    "nom": eq.nom,
                    "num_inventaire": eq.num_inventaire,
                    "nb_pannes": 0,
                    "mtbf_jours": None,
                    "mttr_heures": None,
                })
                continue

            nb_pannes = pannes.count()

            # MTBF : nombre moyen de jours entre pannes consécutives
            dates_cloture = list(pannes.values_list("date_cloture", flat=True))
            if len(dates_cloture) >= 2:
                durees_entre = []
                for i in range(1, len(dates_cloture)):
                    if dates_cloture[i] and dates_cloture[i - 1]:
                        diff = dates_cloture[i] - dates_cloture[i - 1]
                        durees_entre.append(diff.total_seconds() / 86400)
                mtbf = sum(durees_entre) / len(durees_entre) if durees_entre else None
            else:
                mtbf = None

            # MTTR : temps moyen de résolution en heures
            mttr_data = pannes.filter(
                date_qualification__isnull=False,
                date_cloture__isnull=False,
            ).aggregate(
                mttr=Avg(
                    ExpressionWrapper(
                        F("date_cloture") - F("date_signalement"),
                        output_field=DurationField(),
                    )
                )
            )
            mttr = mttr_data["mttr"]
            mttr_heures = mttr.total_seconds() / 3600 if mttr else None

            resultats.append({
                "equipement_id": eq.id,
                "nom": eq.nom,
                "num_inventaire": eq.num_inventaire,
                "nb_pannes": nb_pannes,
                "mtbf_jours": round(mtbf, 1) if mtbf else None,
                "mttr_heures": round(mttr_heures, 1) if mttr_heures else None,
            })

        return Response(resultats)
