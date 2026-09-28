from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import create_audit_log

from .models import DemandeAcces, Etablissement, Notification, User
from .permissions import CanManageUsers
from .scoping import scope_to_etablissement
from .serializers import (
    ChangePasswordSerializer,
    CompleteProfileSerializer,
    DemandeAccesCreateSerializer,
    DemandeAccesSerializer,
    EtablissementSerializer,
    LoginSerializer,
    NotificationSerializer,
    RegisterSerializer,
    RejectDemandeSerializer,
    SetRoleSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """Connexion locale avec JWT."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]

    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    """Création de compte — rôles admin interdits (RB-SEC)."""
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()

    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    """Retourne l'utilisateur courant."""
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Changement de mot de passe."""
    serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data["new_password"])
    request.user.save()
    return Response({"detail": "Mot de passe modifié."})


# --- User Management (Admin only) ---


class UserViewSet(viewsets.ModelViewSet):
    """CRUD Utilisateurs — admin only."""

    queryset = User.objects.select_related("etablissement").all()
    permission_classes = [CanManageUsers]

    def get_queryset(self):
        # Cloisonnement : un admin ne gère que les utilisateurs de son établissement
        return scope_to_etablissement(
            User.objects.select_related("etablissement").all(),
            self.request.user,
            champ="etablissement",
        )

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer

    def perform_create(self, serializer):
        # Un admin ne peut créer un utilisateur que dans son propre établissement
        if self.request.user.etablissement_id:
            serializer.validated_data["etablissement"] = self.request.user.etablissement
        user = serializer.save()
        create_audit_log(
            utilisateur=self.request.user,
            action="user.create",
            entite="User",
            entite_id=user.id,
            nouvelle_valeur={"username": user.username, "role": user.role},
        )

    def perform_update(self, serializer):
        old_data = {"role": serializer.instance.role, "is_active": serializer.instance.is_active}
        user = serializer.save()
        create_audit_log(
            utilisateur=self.request.user,
            action="user.update",
            entite="User",
            entite_id=user.id,
            ancienne_valeur=old_data,
            nouvelle_valeur={"role": user.role, "is_active": user.is_active},
        )

    def perform_destroy(self, instance):
        create_audit_log(
            utilisateur=self.request.user,
            action="user.delete",
            entite="User",
            entite_id=instance.id,
            ancienne_valeur={
                "username": instance.username,
                "email": instance.email,
                "role": instance.role,
                "is_active": instance.is_active,
            },
        )
        instance.delete()


@api_view(["POST"])
@permission_classes([CanManageUsers])
def deactivate_user_view(request, pk):
    """Désactiver un utilisateur (du même établissement)."""
    try:
        target = scope_to_etablissement(
            User.objects.all(), request.user, champ="etablissement"
        ).get(pk=pk)
    except User.DoesNotExist:
        return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if target == request.user:
        return Response(
            {"detail": "Vous ne pouvez pas vous désactiver vous-même."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    old_active = target.is_active
    target.is_active = False
    target.save(update_fields=["is_active"])

    create_audit_log(
        utilisateur=request.user,
        action="user.deactivate",
        entite="User",
        entite_id=target.id,
        ancienne_valeur={"is_active": old_active},
        nouvelle_valeur={"is_active": False},
    )

    return Response({"detail": f"Utilisateur {target.username} désactivé."})


@api_view(["POST"])
@permission_classes([CanManageUsers])
def set_role_view(request, pk):
    """Attribuer un rôle à un utilisateur (du même établissement)."""
    try:
        target = scope_to_etablissement(
            User.objects.all(), request.user, champ="etablissement"
        ).get(pk=pk)
    except User.DoesNotExist:
        return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if target == request.user:
        return Response(
            {"detail": "Vous ne pouvez pas modifier votre propre rôle."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = SetRoleSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)

    old_role = target.role
    target.role = serializer.validated_data["role"]
    target.save(update_fields=["role"])

    create_audit_log(
        utilisateur=request.user,
        action="user.role_change",
        entite="User",
        entite_id=target.id,
        ancienne_valeur={"role": old_role},
        nouvelle_valeur={"role": target.role},
    )

    return Response({"detail": f"Rôle de {target.username} changé en {target.role}."})


# --- Établissement ---


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def etablissement_courant_view(request):
    """Retourne l'établissement de l'utilisateur courant."""
    if request.user.etablissement:
        return Response(EtablissementSerializer(request.user.etablissement).data)
    return Response({"detail": "Aucun établissement associé."}, status=status.HTTP_404_NOT_FOUND)


# --- Demande d'accès ---


@api_view(["POST"])
@permission_classes([AllowAny])
def request_access_view(request):
    """Soumettre une demande d'accès (public)."""
    serializer = DemandeAccesCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    demande = serializer.save()

    return Response(
        {
            "detail": (
                "Votre demande d'accès a été envoyée. Vous recevrez une réponse prochainement."
            ),
            "id": demande.id,
        },
        status=status.HTTP_201_CREATED,
    )


class DemandeAccesViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation des demandes d'accès — admin only.
    Les actions approve/reject sont des endpoints séparés."""

    queryset = DemandeAcces.objects.select_related("traite_par").all()
    serializer_class = DemandeAccesSerializer
    permission_classes = [CanManageUsers]

    def get_queryset(self):
        qs = DemandeAcces.objects.select_related("traite_par").all()
        statut = self.request.query_params.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        return qs


@api_view(["POST"])
@permission_classes([CanManageUsers])
def approve_demande_view(request, pk):
    """Approuver une demande d'accès → crée l'utilisateur."""
    try:
        demande = DemandeAcces.objects.get(pk=pk)
    except DemandeAcces.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if demande.statut != DemandeAcces.Statut.EN_ATTENTE:
        return Response(
            {"detail": "Cette demande a déjà été traitée."}, status=status.HTTP_400_BAD_REQUEST
        )

    # Établissement du nouvel utilisateur : celui de l'admin qui approuve.
    # Un super-admin sans établissement peut en fournir un explicitement.
    etablissement = None
    if not request.user.etablissement_id:
        etab_id = request.data.get("etablissement")
        if etab_id:
            try:
                etablissement = Etablissement.objects.get(pk=etab_id, actif=True)
            except (Etablissement.DoesNotExist, ValueError):
                return Response(
                    {"detail": "Établissement invalide."}, status=status.HTTP_400_BAD_REQUEST
                )

    try:
        user, temp_password = demande.approuver(request.user, etablissement=etablissement)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    create_audit_log(
        utilisateur=request.user,
        action="demande.approve",
        entite="DemandeAcces",
        entite_id=demande.id,
        nouvelle_valeur={"statut": "APPROUVEE", "user_created": user.username},
    )

    return Response(
        {
            "detail": f"Demande approuvée. Utilisateur {user.username} créé. "
            "Communiquez le mot de passe temporaire à l'utilisateur par un canal sûr.",
            "user": UserSerializer(user).data,
            # Transmis à l'administrateur uniquement, jamais persisté en base
            "temp_password": temp_password,
        }
    )


@api_view(["POST"])
@permission_classes([CanManageUsers])
def reject_demande_view(request, pk):
    """Rejeter une demande d'accès."""
    try:
        demande = DemandeAcces.objects.get(pk=pk)
    except DemandeAcces.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if demande.statut != DemandeAcces.Statut.EN_ATTENTE:
        return Response(
            {"detail": "Cette demande a déjà été traitée."}, status=status.HTTP_400_BAD_REQUEST
        )

    serializer = RejectDemandeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    demande.rejeter(request.user, motif=serializer.validated_data.get("motif", ""))

    create_audit_log(
        utilisateur=request.user,
        action="demande.reject",
        entite="DemandeAcces",
        entite_id=demande.id,
        nouvelle_valeur={"statut": "REFUSEE", "motif": demande.motif_rejet},
    )

    return Response({"detail": "Demande rejetée."})


# --- Notifications ---


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications_list_view(request):
    """Lister les notifications de l'utilisateur courant."""
    notifications = request.user.notifications.all()
    non_lues = notifications.filter(lu=False).count()
    data = NotificationSerializer(notifications[:50], many=True).data
    return Response({"notifications": data, "non_lues": non_lues})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notification_read_view(request, pk):
    """Marquer une notification comme lue."""
    try:
        notif = request.user.notifications.get(pk=pk)
    except Notification.DoesNotExist:
        return Response({"detail": "Notification introuvable."}, status=status.HTTP_404_NOT_FOUND)

    notif.marquer_lue()
    return Response({"detail": "Notification marquée comme lue."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notifications_read_all_view(request):
    """Marquer toutes les notifications comme lues."""
    count = request.user.notifications.filter(lu=False).update(lu=True)
    create_audit_log(
        utilisateur=request.user,
        action="notification.read_all",
        entite="Notification",
        entite_id=request.user.id,
        nouvelle_valeur={"count": count},
    )
    return Response({"detail": f"{count} notification(s) marquée(s) comme lue(s)."})


# --- Complétion profil ---


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile_complete_view(request):
    """Vérifier si le profil est complet."""
    return Response(
        {
            "profil_complete": request.user.profil_complete,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_profile_view(request):
    """Compléter le profil après première connexion."""
    if request.user.profil_complete:
        return Response(
            {"detail": "Votre profil est déjà complet."}, status=status.HTTP_400_BAD_REQUEST
        )

    serializer = CompleteProfileSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    request.user.matricule = serializer.validated_data["matricule"]
    request.user.set_password(serializer.validated_data["new_password"])
    request.user.profil_complete = True
    request.user.save(update_fields=["matricule", "profil_complete", "password"])

    create_audit_log(
        utilisateur=request.user,
        action="user.profile_complete",
        entite="User",
        entite_id=request.user.id,
        nouvelle_valeur={"profil_complete": True, "matricule": request.user.matricule},
    )

    return Response(
        {
            "detail": "Profil complété avec succès.",
            "user": UserSerializer(request.user).data,
        }
    )


# --- Listes utilitaires ---


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def etablissements_list_view(request):
    """Lister les établissements actifs."""
    etabs = Etablissement.objects.filter(actif=True).values("id", "nom")
    return Response(list(etabs))
