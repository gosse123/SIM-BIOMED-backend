"""Synchronisation du statut opérationnel de l'équipement (RB-CL-002, RB-EQ-003).

Le statut opérationnel suit le cycle de vie des pannes et interventions :
le serveur est l'autorité (RB-003) et chaque changement est audité (RB-AUD-001).
"""

from apps.audit.models import create_audit_log

# Statuts source autorisés pour chaque cible — évite les sauts incohérents
# (ex. : un équipement réformé ne repasse jamais en fonctionnement).
SOURCES_AUTORISEES = {
    # Retour en panne : après intervention partielle/annulée ou reprise
    # depuis une attente pièce/prestataire.
    "EN_PANNE": {
        "FONCTIONNEL",
        "FONCTIONNEL_SOUS_SURVEILLANCE",
        "EN_MAINTENANCE",
        "EN_ATTENTE_PIECE_OU_PRESTATAIRE",
    },
    # Prise en main : depuis l'état de fonctionnement, la panne ou la
    # reprise d'une attente pièce/prestataire.
    "EN_MAINTENANCE": {
        "FONCTIONNEL",
        "FONCTIONNEL_SOUS_SURVEILLANCE",
        "EN_PANNE",
        "EN_ATTENTE_PIECE_OU_PRESTATAIRE",
    },
    "EN_ATTENTE_PIECE_OU_PRESTATAIRE": {
        "FONCTIONNEL",
        "FONCTIONNEL_SOUS_SURVEILLANCE",
        "EN_PANNE",
        "EN_MAINTENANCE",
    },
    "FONCTIONNEL": {
        "FONCTIONNEL",
        "FONCTIONNEL_SOUS_SURVEILLANCE",
        "EN_PANNE",
        "EN_MAINTENANCE",
        "EN_ATTENTE_PIECE_OU_PRESTATAIRE",
        "HORS_SERVICE",
    },
    "FONCTIONNEL_SOUS_SURVEILLANCE": {
        "FONCTIONNEL",
        "FONCTIONNEL_SOUS_SURVEILLANCE",
        "EN_PANNE",
        "EN_MAINTENANCE",
        "EN_ATTENTE_PIECE_OU_PRESTATAIRE",
        "HORS_SERVICE",
    },
}


def synchroniser_statut(equipement, cible: str, utilisateur, motif: str) -> bool:
    """Passe l'équipement au statut `cible` si la transition est cohérente.

    Retourne True si le statut a changé. Aucun effet si l'équipement est
    déjà à la cible, réformé, ou si la source n'est pas autorisée.
    """
    actuel = equipement.etat_operationnel
    if actuel == cible or actuel == "REFORME":
        return False
    if actuel not in SOURCES_AUTORISEES.get(cible, set()):
        return False

    equipement.etat_operationnel = cible
    equipement.save(update_fields=["etat_operationnel"])
    create_audit_log(
        utilisateur=utilisateur,
        action="equipment.statut_change",
        entite="Equipment",
        entite_id=equipement.id,
        ancienne_valeur={"etat_operationnel": actuel},
        nouvelle_valeur={"etat_operationnel": cible, "motif": motif},
    )
    return True
