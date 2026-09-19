from django.urls import path
from .views import WorkQueueView

app_name = "workqueue"

urlpatterns = [
    path("workqueue/", WorkQueueView.as_view(), name="workqueue-list"),
]
