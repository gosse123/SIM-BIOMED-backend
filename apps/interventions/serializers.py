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
    # Champ métier (hors modèle) : si vrai, l'équipement passe HORS_SERVICE
    # à la création de l'intervention (RB-CL-002 — cohérence du statut).
    hors_service_total = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Intervention
        fields = (
            "panne",
            "equipement",
            "type_intervention",
            "description",
            "pieces_utilisees",
            "hors_service_total",
        )

    def validate_equipement(self, value):
        from apps.equipment.models import Equipment

        if value.etat_operationnel == Equipment.StatutOperationnel.REFORME:
            raise serializers.ValidationError("Pas d'intervention sur un équipement réformé.")
        # Cloisonnement : pas d'intervention sur l'équipement d'un autre établissement
        request = self.context.get("request")
        if (
            request
            and request.user.etablissement_id
            and value.etablissement_id != request.user.etablissement_id
        ):
            raise serializers.ValidationError(
                "Cet équipement n'appartient pas à votre établissement."
            )
        return value

    def validate_panne(self, value):
        # Cloisonnement identique sur la panne liée éventuelle
        request = self.context.get("request")
        if (
            value
            and request
            and request.user.etablissement_id
            and value.equipement.etablissement_id != request.user.etablissement_id
        ):
            raise serializers.ValidationError("Cette panne n'appartient pas à votre établissement.")
        return value


class StartInterventionSerializer(serializers.Serializer):
    pass


class FinishInterventionSerializer(serializers.ModelSerializer):
    # Champ métier (hors modèle) : si vrai, l'équipement repasse FONCTIONNEL
    # à la terminaison (RB-CL-002). Sans effet sur la panne liée éventuelle :
    # sa clôture exige toujours un résultat de test (RB-CL-001).
    repare_totalement = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Intervention
        fields = ("temps_passe_minutes", "pieces_utilisees", "repare_totalement")
