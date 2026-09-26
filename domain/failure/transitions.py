"""Règles de transition du cycle de vie des pannes (RB-004, RB-005, RB-CL-001).

Couche domaine : aucune dépendance à Django REST, aux vues ou à HTTP.
Testable en isolation.

RB-004 : Pas de transition implicite — seules les transitions déclarées ici
sont autorisées.
RB-005 / RB-TEST-001 / RB-CL-001 : une panne ne peut passer à CLOSE que depuis
EN_TEST, après un résultat de test.
"""

TRANSITIONS_AUTORISEES = {
    "SIGNALEE": {"QUALIFIEE"},
    "QUALIFIEE": {"CRITICITE_EVALUEE"},
    "CRITICITE_EVALUEE": {"EN_DIAGNOSTIC"},
    "EN_DIAGNOSTIC": {"EN_INTERVENTION", "EN_ATTENTE_PIECE", "EN_ATTENTE_PRESTATAIRE"},
    "EN_INTERVENTION": {"EN_TEST", "EN_ATTENTE_PIECE", "EN_ATTENTE_PRESTATAIRE"},
    # Règle §14 : l'attente (pièce/prestataire) est accessible pendant le
    # diagnostic ou l'intervention, et la reprise ramène à l'intervention.
    "EN_ATTENTE_PIECE": {"EN_INTERVENTION"},
    "EN_ATTENTE_PRESTATAIRE": {"EN_INTERVENTION"},
    "EN_TEST": {"CLOSE"},
    "CLOSE": set(),
}


class TransitionInvalide(ValueError):
    """Transition de statut non autorisée (RB-004)."""


def verifier_transition(ancien_statut: str, nouveau_statut: str) -> None:
    """Lève TransitionInvalide si la transition n'est pas déclarée.

    RB-CL-001 : CLOSE exige EN_TEST (donc un test réalisé) — garanti par la
    carte des transitions, pas seulement par les vues.
    """
    if nouveau_statut not in TRANSITIONS_AUTORISEES.get(ancien_statut, set()):
        raise TransitionInvalide(
            f"Transition non autorisée : {ancien_statut} → {nouveau_statut}"
        )
