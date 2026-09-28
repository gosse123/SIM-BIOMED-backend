from rest_framework import serializers

from .models import MaintenancePlan, MaintenancePreventive


class MaintenancePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenancePlan
        fields = (
            "id",
            "nom",
            "description",
            "type_equipement",
            "frequence",
            "delai_jours",
            "created_at",
        )


class MaintenancePreventiveListSerializer(serializers.ModelSerializer):
    plan_nom = serializers.CharField(source="plan.nom", read_only=True)
    equipement_nom = serializers.CharField(source="equipement.nom", read_only=True)

    class Meta:
        model = MaintenancePreventive
        fields = (
            "id",
            "plan",
            "plan_nom",
            "equipement",
            "equipement_nom",
            "statut",
            "date_planifiee",
            "date_effective",
            "created_at",
        )


class MaintenancePreventiveDetailSerializer(serializers.ModelSerializer):
    plan_detail = MaintenancePlanSerializer(source="plan", read_only=True)
    equipement_nom = serializers.CharField(source="equipement.nom", read_only=True)

    class Meta:
        model = MaintenancePreventive
        fields = (
            "id",
            "plan",
            "plan_detail",
            "equipement",
            "equipement_nom",
            "statut",
            "date_planifiee",
            "date_effective",
            "realisee_par",
            "commentaire",
            "created_at",
            "updated_at",
        )


class CreateMaintenancePreventiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenancePreventive
        fields = ("plan", "equipement", "date_planifiee")


class FinishMaintenanceSerializer(serializers.Serializer):
    commentaire = serializers.CharField(required=False, allow_blank=True)
