import json
from datetime import timedelta

from celery import shared_task
import time
import random
import hashlib

from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone

from myapp.models import Webhook


@shared_task(bind=True)
def send_data_task(self, data):
    try:
        time.sleep(5)
        result = random.randint(0, 50)
        if result <= 10:
            raise ValueError('Ошибка')

        data_str = json.dumps(data).encode('utf-8')
        md5_result = hashlib.md5(data_str).hexdigest()

        return {'number': result, 'md5': md5_result}
    except ValueError:
        try:
            self.retry(countdown=5, max_retries=5)
        except MaxRetriesExceededError:
            return {"error": "Максимальное количество попыток превышено"}


@shared_task
def delete_old_webhooks():
    time_threshold = timezone.now() - timedelta(hours=4)
    Webhook.objects.filter(created_at__lt=time_threshold).delete()
