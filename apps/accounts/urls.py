from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "accounts"

router = DefaultRouter()
router.register(r"users", views.UserViewSet)
router.register(r"demandes", views.DemandeAccesViewSet)

urlpatterns = [
    path("auth/login/", views.login_view, name="login"),
    path("auth/register/", views.register_view, name="register"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", views.me_view, name="me"),
    path("auth/change-password/", views.change_password_view, name="change_password"),
    path("auth/etablissement/", views.etablissement_courant_view, name="etablissement_courant"),
    path("auth/request-access/", views.request_access_view, name="request_access"),
    path("auth/profile-complete/", views.profile_complete_view, name="profile_complete"),
    path("auth/complete-profile/", views.complete_profile_view, name="complete_profile"),
    path("auth/etablissements/", views.etablissements_list_view, name="etablissements_list"),
    path("users/<int:pk>/deactivate/", views.deactivate_user_view, name="user_deactivate"),
    path("users/<int:pk>/set-role/", views.set_role_view, name="user_set_role"),
    path("demandes/<int:pk>/approve/", views.approve_demande_view, name="demande_approve"),
    path("demandes/<int:pk>/reject/", views.reject_demande_view, name="demande_reject"),
    path("notifications/", views.notifications_list_view, name="notifications_list"),
    path("notifications/<int:pk>/read/", views.notification_read_view, name="notification_read"),
    path("notifications/read-all/", views.notifications_read_all_view, name="notifications_read_all"),
    path("", include(router.urls)),
]
