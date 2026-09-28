from rest_framework import serializers

from .models import Equipment, Localisation, Service


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id", "nom", "description")


class LocalisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Localisation
        fields = ("id", "batiment", "etage", "salle")


class EquipmentListSerializer(serializers.ModelSerializer):
    service_nom = serializers.CharField(source="service.nom", read_only=True)
    localisation_str = serializers.SerializerMethodField()

    class Meta:
        model = Equipment
        fields = (
            "id",
            "num_inventaire",
            "nom",
            "type_equipement",
            "categorie",
            "marque",
            "modele",
            "service",
            "service_nom",
            "localisation",
            "localisation_str",
            "etat_operationnel",
            "niveau_criticite",
            "statut_cycle_vie",
            "created_at",
        )

    def get_localisation_str(self, obj):
        return str(obj.localisation)


class EquipmentDetailSerializer(serializers.ModelSerializer):
    service_detail = ServiceSerializer(source="service", read_only=True)
    localisation_detail = LocalisationSerializer(source="localisation", read_only=True)

    class Meta:
        model = Equipment
        fields = (
            "id",
            "num_inventaire",
            "nom",
            "type_equipement",
            "categorie",
            "marque",
            "modele",
            "num_serie",
            "service",
            "service_detail",
            "localisation",
            "localisation_detail",
            "date_reception",
            "date_installation",
            "date_mise_service",
            "etat_operationnel",
            "niveau_criticite",
            "statut_cycle_vie",
            "created_at",
            "updated_at",
        )
