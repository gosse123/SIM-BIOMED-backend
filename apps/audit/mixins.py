"""Mixins partagés pour les vues avec création auditée (RB-AUD-001)."""
from rest_framework import status
from rest_framework.response import Response

from .models import create_audit_log


class AuditedCreateMixin:
    """Standardise create() : validation, sauvegarde, audit, réponse détaillée.

    La sous-classe doit définir :
    - audit_create_action : str (ex. "intervention.create")
    - audit_entite : str (ex. "Intervention")
    - detail_serializer_class : serializer de lecture détaillée
    - get_audit_nouvelle_valeur(instance) : dict des valeurs tracées (optionnel)
    """

    audit_create_action = None
    audit_entite = None
    detail_serializer_class = None

    def get_audit_nouvelle_valeur(self, instance):
        return {}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        create_audit_log(
            utilisateur=request.user,
            action=self.audit_create_action,
            entite=self.audit_entite,
            entite_id=instance.id,
            nouvelle_valeur=self.get_audit_nouvelle_valeur(instance),
        )
        return Response(
            self.detail_serializer_class(instance).data,
            status=status.HTTP_201_CREATED,
        )
