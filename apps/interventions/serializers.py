from rest_framework import serializers
from .models import Intervention


class InterventionListSerializer(serializers.ModelSerializer):
    equipement_nom = serializers.CharField(source="equipement.nom", read_only=True)
    realisee_par_nom = serializers.SerializerMethodField()
    panne_id = serializers.IntegerField(source="panne.id", read_only=True, default=None)

    class Meta:
        model = Intervention
        fields = (
            "id",
            "panne_id",
            "equipement",
            "equipement_nom",
            "type_intervention",
            "statut",
            "date_debut",
            "date_fin",
            "temps_passe_minutes",
            "realisee_par",
            "realisee_par_nom",
            "created_at",
        )

    def get_realisee_par_nom(self, obj):
        if obj.realisee_par:
            return f"{obj.realisee_par.first_name} {obj.realisee_par.last_name}"
        return None


class InterventionDetailSerializer(serializers.ModelSerializer):
    equipement_nom = serializers.CharField(source="equipement.nom", read_only=True)
    realisee_par_nom = serializers.SerializerMethodField()
    panne_id = serializers.IntegerField(source="panne.id", read_only=True, default=None)

    class Meta:
        model = Intervention
        fields = (
            "id",
            "panne_id",
            "equipement",
            "equipement_nom",
            "type_intervention",
            "statut",
            "description",
            "pieces_utilisees",
            "temps_passe_minutes",
            "date_debut",
            "date_fin",
            "realisee_par",
            "realisee_par_nom",
            "created_at",
            "updated_at",
        )

    def get_realisee_par_nom(self, obj):
        if obj.realisee_par:
            return f"{obj.realisee_par.first_name} {obj.realisee_par.last_name}"
        return None


class CreateInterventionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intervention
        fields = ("panne", "equipement", "type_intervention", "description", "pieces_utilisees")

    def validate_equipement(self, value):
        from apps.equipment.models import Equipment
        if value.etat_operationnel == Equipment.StatutOperationnel.REFORME:
            raise serializers.ValidationError("Pas d'intervention sur un équipement réformé.")
        return value


class StartInterventionSerializer(serializers.Serializer):
    pass


class FinishInterventionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intervention
        fields = ("temps_passe_minutes", "pieces_utilisees")
