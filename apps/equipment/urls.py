from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"equipment", views.EquipmentViewSet, basename="equipment")
router.register(r"services", views.ServiceViewSet)
router.register(r"locations", views.LocalisationViewSet)

app_name = "equipment"

urlpatterns = [
    path("", include(router.urls)),
]
