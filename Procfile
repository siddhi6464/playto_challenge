web: gunicorn playto_payouts.wsgi --log-file -
worker: celery -A playto_payouts worker -l info
beat: celery -A playto_payouts beat -l info
