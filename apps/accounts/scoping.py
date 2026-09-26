"""Cloisonnement multi-établissements des données (RB-SEC).

Règle : un utilisateur rattaché à un établissement ne voit et ne manipule
que les données de son établissement. Un utilisateur sans établissement
(super-admin d'onboarding) voit tout — nécessaire pour le provisionnement
initial d'un nouvel établissement.
"""

def scope_to_etablissement(queryset, user, champ="equipement__etablissement"):
    """Filtre un queryset sur l'établissement de l'utilisateur.

    champ : chemin ORM vers la FK Etablissement (ex. "etablissement",
    "equipement__etablissement", "service__etablissement").
    """
    if getattr(user, "etablissement_id", None):
        return queryset.filter(**{champ: user.etablissement_id})
    return queryset
