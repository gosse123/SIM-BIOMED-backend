from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def check_overdue_maintenance():
    """
    Vérifie les maintenances préventives en retard (RB-MP-001).
    Exécuté quotidiennement via Celery Beat.
    """
    from apps.preventive.models import MaintenancePreventive

    today = timezone.now().date()
    overdue = MaintenancePreventive.objects.filter(
        statut=MaintenancePreventive.Statut.PLANIFIEE,
        date_planifiee__lt=today,
    )

    count = 0
    for mp in overdue:
        mp.statut = MaintenancePreventive.Statut.EN_RETARD
        mp.save()
        count += 1

    return f"{count} maintenance(s) préventive(s) marquée(s) en retard."


@shared_task
def generate_preventive_schedule():
    """
    Génère les maintenances préventives futures à partir des plans actifs.
    Exécuté mensuellement via Celery Beat.
    """
    from apps.equipment.models import Equipment
    from apps.preventive.models import MaintenancePlan, MaintenancePreventive

    plans = MaintenancePlan.objects.all()
    today = timezone.now().date()
    created = 0

    for plan in plans:
        equipements = Equipment.objects.filter(
            type_equipement=plan.type_equipement,
            etat_operationnel__in=[
                Equipment.StatutOperationnel.FONCTIONNEL,
                Equipment.StatutOperationnel.FONCTIONNEL_SOUS_SURVEILLANCE,
            ],
        )

        for eq in equipements:
            # Vérifier si une maintenance est déjà planifiée dans le prochain cycle
            next_date = today + timedelta(days=plan.delai_jours)
            exists = MaintenancePreventive.objects.filter(
                plan=plan, equipement=eq, date_planifiee__gte=today
            ).exists()

            if not exists:
                MaintenancePreventive.objects.create(
                    plan=plan, equipement=eq, date_planifiee=next_date
                )
                created += 1

    return f"{created} maintenance(s) préventive(s) générée(s)."
