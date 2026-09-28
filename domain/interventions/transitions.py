"""Règles de transition du cycle de vie des interventions (RB-004, RB-IN-001).

Couche domaine : aucune dépendance à Django, aux vues ou à HTTP.
Testable en isolation.

RB-IN-001 : une intervention a une trace de début et de fin — les transitions
déclarées ici encadrent démarrage, fin et annulation.
RB-004 : pas de transition implicite.
"""

TRANSITIONS_AUTORISEES = {
    "PLANIFIEE": {"EN_COURS", "ANNULEE"},
    "EN_COURS": {"TERMINEE", "ANNULEE"},
    "TERMINEE": set(),
    "ANNULEE": set(),
}


class TransitionInterventionInvalideError(ValueError):
    """Transition de statut d'intervention non autorisée (RB-004)."""


def verifier_transition(ancien_statut: str, nouveau_statut: str) -> None:
    """Lève TransitionInterventionInvalideError si la transition n'est pas déclarée."""
    if nouveau_statut not in TRANSITIONS_AUTORISEES.get(ancien_statut, set()):
        raise TransitionInterventionInvalideError(
            f"Transition non autorisée : {ancien_statut} → {nouveau_statut}"
        )
