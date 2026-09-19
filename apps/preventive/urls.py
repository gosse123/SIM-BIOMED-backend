from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"maintenance-plans", views.MaintenancePlanViewSet)
router.register(r"maintenance-preventive", views.MaintenancePreventiveViewSet)

app_name = "preventive"

urlpatterns = [
    path("", include(router.urls)),
]
