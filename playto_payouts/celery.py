import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'playto_payouts.settings')

app = Celery('playto_payouts')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
