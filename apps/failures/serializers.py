from rest_framework import serializers
from django.utils import timezone
from .models import Panne
from apps.accounts.serializers import UserSerializer
from apps.equipment.serializers import EquipmentListSerializer


class PanneListSerializer(serializers.ModelSerializer):
    equipement_nom = serializers.CharField(source="equipement.nom", read_only=True)
    equipement_num = serializers.CharField(source="equipement.num_inventaire", read_only=True)
    signale_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = Panne
        fields = (
            "id",
            "equipement",
            "equipement_nom",
            "equipement_num",
            "statut",
            "niveau_criticite",
            "date_signalement",
            "signale_par",
            "signale_par_nom",
            "resultat_test",
            "created_at",
        )

    def get_signale_par_nom(self, obj):
        return f"{obj.signale_par.first_name} {obj.signale_par.last_name}"


class PanneDetailSerializer(serializers.ModelSerializer):
    equipement_detail = EquipmentListSerializer(source="equipement", read_only=True)
    signale_par_detail = UserSerializer(source="signale_par", read_only=True)
    qualifiee_par_detail = UserSerializer(source="qualifiee_par", read_only=True)
    diagnostique_par_detail = UserSerializer(source="diagnostique_par", read_only=True)
    cloturee_par_detail = UserSerializer(source="cloturee_par", read_only=True)
    transitions_valides = serializers.SerializerMethodField()

    class Meta:
        model = Panne
        fields = (
            "id",
            "equipement",
            "equipement_detail",
            "date_signalement",
            "signale_par",
            "signale_par_detail",
            "description_signalement",
            "date_qualification",
            "qualifiee_par",
            "qualifiee_par_detail",
            "observation_qualification",
            "critere_urgence",
            "statut",
            "critere_impact",
            "critere_criticite",
            "niveau_criticite",
            "date_diagnostic",
            "diagnostique_par",
            "diagnostique_par_detail",
            "description_diagnostic",
            "cause_identifiee",
            "resultat_test",
            "date_cloture",
            "cloturee_par",
            "cloturee_par_detail",
            "commentaire_cloture",
            "created_at",
            "updated_at",
            "transitions_valides",
        )

    def get_transitions_valides(self, obj):
        return [t.value for t in Panne.TRANSITIONS_VALIDES.get(obj.statut, [])]


class ReportPanneSerializer(serializers.ModelSerializer):
    """Signalement de panne (etats.SIGNALEE)."""

    class Meta:
        model = Panne
        fields = ("equipement", "description_signalement")

    def validate_equipement(self, value):
        from apps.equipment.models import Equipment
        if value.etat_operationnel == Equipment.StatutOperationnel.REFORME:
            raise serializers.ValidationError("Impossible de signaler une panne sur un equipement reforme.")
        return value

    def create(self, validated_data):
        validated_data["signale_par"] = self.context["request"].user
        return super().create(validated_data)


class QualifyPanneSerializer(serializers.ModelSerializer):
    """Qualification de panne — observation obligatoire (RB-PANNE-001)."""

    class Meta:
        model = Panne
        fields = ("observation_qualification", "critere_urgence")

    def validate_observation_qualification(self, value):
        if not value.strip():
            raise serializers.ValidationError("L'observation de qualification est obligatoire.")
        return value

    def validate(self, attrs):
        panne = self.instance
        if panne.statut != Panne.Statut.SIGNALEE:
            raise serializers.ValidationError("Seules les pannes en etat SIGNALEE peuvent etre qualifiees.")
        return attrs


class EvaluateCriticiteSerializer(serializers.ModelSerializer):
    """Evaluation de criticite — critere impact obligatoire."""

    class Meta:
        model = Panne
        fields = ("critere_impact", "critere_criticite", "niveau_criticite")

    def validate(self, attrs):
        panne = self.instance
        if panne.statut != Panne.Statut.QUALIFIEE:
            raise serializers.ValidationError("Seules les pannes QUALIFIEES peuvent avoir leur criticite evaluee.")
        return attrs


class DiagnosePanneSerializer(serializers.ModelSerializer):
    """Diagnostic — description et cause obligatoires (RB-DIAG-001)."""

    class Meta:
        model = Panne
        fields = ("description_diagnostic", "cause_identifiee")

    def validate(self, attrs):
        panne = self.instance
        if panne.statut != Panne.Statut.CRITICITE_EVALUEE:
            raise serializers.ValidationError("Seules les pannes avec criticite evaluee peuvent etre diagnostiquees.")
        if not attrs.get("description_diagnostic", "").strip():
            raise serializers.ValidationError({"description_diagnostic": "Le diagnostic est obligatoire."})
        if not attrs.get("cause_identifiee", "").strip():
            raise serializers.ValidationError({"cause_identifiee": "La cause identifiee est obligatoire."})
        return attrs


class StartInterventionSerializer(serializers.Serializer):
    """Demarrage d'intervention — declenche EN_INTERVENTION."""
    pass


class WaitPieceSerializer(serializers.Serializer):
    """Mise en attente de piece."""
    pass


class WaitPrestataireSerializer(serializers.Serializer):
    """Mise en attente de prestataire."""
    pass


class StartTestSerializer(serializers.ModelSerializer):
    """Lancement du test (RB-TEST-001)."""
    class Meta:
        model = Panne
        fields = ("resultat_test",)

    def validate(self, attrs):
        panne = self.instance
        if panne.statut != Panne.Statut.EN_INTERVENTION:
            raise serializers.ValidationError("Le test ne peut etre lance qu'en etat EN_INTERVENTION.")
        return attrs


class ClosePanneSerializer(serializers.Serializer):
    """Cloture — verification du test conforme (RB-CL-001)."""
    commentaire_cloture = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        panne = self.instance
        if panne.resultat_test not in (
            Panne.ResultatTest.CONFORME,
            Panne.ResultatTest.SOUS_SURVEILLANCE,
        ):
            raise serializers.ValidationError(
                "Impossible de cloturer : le test doit etre CONFORME ou SOUS_SURVEILLANCE (RB-CL-001)."
            )
        return attrs
