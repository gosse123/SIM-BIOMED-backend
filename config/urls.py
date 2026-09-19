from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.equipment.urls")),
    path("api/", include("apps.failures.urls")),
    path("api/", include("apps.interventions.urls")),
    path("api/", include("apps.workqueue.urls")),
    path("api/", include("apps.preventive.urls")),
    path("api/", include("apps.indicators.urls")),
    path("api/", include("apps.dashboard.urls")),
]
