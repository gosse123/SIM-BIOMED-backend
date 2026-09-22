from django.db import migrations


def create_default_establishment(apps, schema_editor):
    """Crée l'établissement par défaut et assigne les données existantes."""
    Etablissement = apps.get_model("accounts", "Etablissement")
    User = apps.get_model("accounts", "User")
    Equipment = apps.get_model("equipment", "Equipment")
    Service = apps.get_model("equipment", "Service")
    Localisation = apps.get_model("equipment", "Localisation")

    # Créer l'établissement par défaut
    etab, _ = Etablissement.objects.get_or_create(
        nom="Site Central — Hôpital Nord",
        defaults={"adresse": "", "actif": True},
    )

    # Assigner aux utilisateurs existants sans établissement
    User.objects.filter(etablissement__isnull=True).update(etablissement=etab)

    # Assigner aux équipements existants sans établissement
    Equipment.objects.filter(etablissement__isnull=True).update(etablissement=etab)

    # Assigner aux services existants sans établissement
    Service.objects.filter(etablissement__isnull=True).update(etablissement=etab)

    # Assigner aux localisations existantes sans établissement
    Localisation.objects.filter(etablissement__isnull=True).update(etablissement=etab)


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_etablissement_user_etablissement"),
        ("equipment", "0002_equipment_etablissement_localisation_etablissement_and_more"),
    ]

    operations = [
        migrations.RunPython(create_default_establishment, reverse_func),
    ]
