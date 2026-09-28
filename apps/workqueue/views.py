from django.db.models import Case, Count, IntegerField, Value, When
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.scoping import scope_to_etablissement
from apps.failures.models import Panne
from apps.interventions.models import Intervention


class WorkQueueView(APIView):
    """
    File de travail : pannes ouvertes priorisées par criticité.
    RB-FIL-001 : Les pannes critiques passent en premier.
    RB-PR-004 : file ordonnée, transitions et affectation pilotées serveur.
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
            .select_related("equipement", "equipement__service", "signale_par", "affecte_a")
            .order_by(
                # Priorisation par criticité réelle (RB-PR-004) : CRITIQUE
                # d'abord — pas de tri alphabétique.
                Case(
                    When(niveau_criticite="CRITIQUE", then=Value(0)),
                    When(niveau_criticite="ELEVE", then=Value(1)),
                    When(niveau_criticite="MOYEN", then=Value(2)),
                    When(niveau_criticite="FAIBLE", then=Value(3)),
                    default=Value(9),
                    output_field=IntegerField(),
                ),
                "-created_at",
            )
        )

        # NB : order_by() doit être neutralisé pour l'agrégat, sinon Django
        # ajoute le tri au GROUP BY et chaque ligne devient son propre groupe.
        stats = {
            "total_ouvertes": pannes_ouvertes.count(),
            "par_statut": {
                row[0]: row[1]
                for row in pannes_ouvertes.order_by().values_list("statut").annotate(
                    count=Count("id")
                )
            },
            "par_criticite": {
                row[0]: row[1]
                for row in pannes_ouvertes.order_by()
                .values_list("niveau_criticite")
                .annotate(count=Count("id"))
            },
            "pannes": [
                {
                    "id": p.id,
                    "equipement_nom": p.equipement.nom,
                    "equipement_num": p.equipement.num_inventaire,
                    "service_nom": p.equipement.service.nom if p.equipement.service else None,
                    "statut": p.statut,
                    "niveau_criticite": p.niveau_criticite,
                    "date_signalement": p.date_signalement.isoformat(),
                    "signale_par_nom": f"{p.signale_par.first_name} {p.signale_par.last_name}",
                    "description_signalement": p.description_signalement[:100],
                    "cause_identifiee": (p.cause_identifiee or "")[:100],
                    # RB-004 : transitions calculées par le serveur, le
                    # client ne décide pas de ce qui est autorisé.
                    "transitions_valides": [
                        t.value for t in Panne.TRANSITIONS_VALIDES.get(p.statut, [])
                    ],
                    "affecte_a": p.affecte_a_id,
                    "affecte_a_nom": (
                        p.affecte_a.get_full_name().strip() or p.affecte_a.username
                        if p.affecte_a
                        else None
                    ),
                }
                for p in pannes_ouvertes
            ],
        }

        # Âge moyen d'ouverture (indicateur temps réel, pas de SLA codé en dur)
        ages = [
            (timezone.now() - dt).total_seconds() / 60
            for dt in pannes_ouvertes.values_list("date_signalement", flat=True)
        ]
        stats["age_moyen_minutes"] = round(sum(ages) / len(ages)) if ages else None

        # Garde biomédicale : techniciens réels de l'établissement + charge
        techniciens = scope_to_etablissement(
            User.objects.filter(
                role__in=[
                    User.Role.TECHNICIEN,
                    User.Role.RESPONSABLE_BIOMEDICAL,
                    User.Role.ADMINISTRATEUR,
                ],
                is_active=True,
            ),
            request.user,
            champ="etablissement",
        )
        en_cours_par_user = dict(
            scope_to_etablissement(
                Intervention.objects.filter(statut="EN_COURS"), request.user
            )
            .values_list("realisee_par_id")
            .annotate(count=Count("id"))
        )
        charge_totale = sum(en_cours_par_user.values()) or 1
        stats["techniciens"] = [
            {
                "id": u.id,
                "nom": u.get_full_name().strip() or u.username,
                "initiales": (
                    f"{u.first_name[:1]}{u.last_name[:1]}".upper()
                    if u.first_name and u.last_name
                    else u.username[:2].upper()
                ),
                "interventions_en_cours": en_cours_par_user.get(u.id, 0),
                "charge": round(100 * en_cours_par_user.get(u.id, 0) / charge_totale),
            }
            for u in techniciens
        ]

        return Response(stats)
