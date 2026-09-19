from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"pannes", views.PanneViewSet)

app_name = "failures"

urlpatterns = [
    path("", include(router.urls)),
]
