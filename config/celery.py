import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("sim_biomed")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "check-overdue-maintenance-daily": {
        "task": "apps.preventive.tasks.check_overdue_maintenance",
        "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(hour=6, minute=0),
    },
    "generate-preventive-schedule-monthly": {
        "task": "apps.preventive.tasks.generate_preventive_schedule",
        "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(
            day_of_month=1, hour=7, minute=0
        ),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
