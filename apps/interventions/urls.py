from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"interventions", views.InterventionViewSet)

app_name = "interventions"

urlpatterns = [
    path("", include(router.urls)),
]
