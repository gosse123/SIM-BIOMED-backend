from django.urls import path
from .views import IndicateursView

app_name = "indicators"

urlpatterns = [
    path("indicateurs/", IndicateursView.as_view(), name="indicateurs"),
]
