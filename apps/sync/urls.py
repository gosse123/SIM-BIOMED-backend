from django.urls import path
from . import views

app_name = "sync"

urlpatterns = [
    path("sync/status/", views.sync_status, name="sync-status"),
    path("sync/retry/", views.retry_failed, name="sync-retry"),
]
