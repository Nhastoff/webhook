from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from myapp.models import Webhook
from myapp.serializers import WebhookSerializer
from myapp.tasks import send_data_task, delete_old_webhooks
from myapp.tests.fabrics import UserFactory, WebhookFactory


@pytest.fixture
def api_client():
    client = APIClient()
    user = UserFactory()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
class TestWebhookCreateView:

    def test_create_webhook_success(self, api_client):
        client, _ = api_client
        data = {'data': {'key': 'value'}}
        response = client.post('/webhook/', data=data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_webhook_invalid_data(self, api_client):
        client, _ = api_client
        response = client.post('/webhook/', {'data': 'invalid'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestWebhookWriteView:

    def test_write_webhook_success(self, api_client):
        client, user = api_client
        webhook = WebhookFactory(user=user)
        response = client.post(f'/webhook/{webhook.id}/write/', {'data': 'new_data'})
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_write_webhook_not_found(self, api_client):
        client, _ = api_client
        response = client.post('/webhook/999/write/', {'data': 'new_data'})
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestWebhookViewSet:
    def test_list_webhooks(self):
        client = APIClient()
        user = UserFactory()
        WebhookFactory.create_batch(5, user=user)
        client.force_authenticate(user=user)
        response = client.get('/webhook/list/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5


@pytest.mark.django_db
class TestWebhookDetailView:
    def test_retrieve_webhook(self, api_client):
        client, user = api_client
        webhook = WebhookFactory(user=user)
        response = client.get(reverse("webhook-detail", args=[webhook.id]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookSerializer(webhook).data

    def test_delete_webhook(self, api_client):
        client, user = api_client
        webhook = WebhookFactory(user=user)
        response = client.delete(reverse("webhook-detail", args=[webhook.id]))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Webhook.objects.filter(id=webhook.id).exists()

    def test_unauthorized_access(self, api_client):
        client, user = api_client
        webhook = WebhookFactory(user=user)
        client.force_authenticate(user=None)
        response = client.get(reverse("webhook-detail", args=[webhook.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestTaskResultView:

    @patch('myapp.views.send_data_task')
    def test_get_result_ready(self, mock_task, api_client):
        client, _ = api_client
        mock_task.AsyncResult.return_value.ready.return_value = True
        mock_task.AsyncResult.return_value.get.return_value = "Result"

        response = client.get(reverse('task-result', args=['123asfas']))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {'result': 'Result'}

    @patch('myapp.views.send_data_task')
    def test_get_result_pending(self, mock_task, api_client):
        client, _ = api_client
        mock_task.AsyncResult.return_value.ready.return_value = False

        response = client.get(reverse('task-result', args=['123asfas']))
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data == {'status': 'pending'}

    def test_unauthorized_access(self, api_client):
        client, _ = api_client
        client.force_authenticate(user=None)
        response = client.get(reverse('task-result', args=['123asfas']))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('myapp.views.send_data_task')
    def test_celery_task_call(self, mock_send_data_task, api_client):
        client, _ = api_client
        mock_result = MagicMock()
        mock_result.ready.return_value = True
        mock_result.get.return_value = "some result"
        mock_send_data_task.AsyncResult.return_value = mock_result

        response = client.get(reverse('task-result', args=['123asfas']))

        mock_send_data_task.AsyncResult.assert_called_once_with('123asfas')

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {'result': 'some result'}


@pytest.mark.django_db
def test_send_data_task_success():
    with (
        patch('myapp.tasks.random.randint', return_value=20),
        patch('myapp.tasks.time.sleep') as mock_sleep
    ):
        result = send_data_task(data={'key': 'value'})
        assert 'number' in result
        assert 'md5' in result
        mock_sleep.assert_called_once_with(5)


@pytest.mark.django_db
def test_send_data_task_retry():
    with (
        patch('myapp.tasks.random.randint', return_value=10),
        patch('myapp.tasks.send_data_task.retry') as mock_retry,
        patch('myapp.tasks.time.sleep') as mock_sleep
    ):
        try:
            send_data_task(data={'key': 'value'})
        except ValueError:
            pass
        mock_retry.assert_called()


@pytest.mark.django_db
def test_send_data_task_max_retries_exceeded():
    with (
        patch('myapp.tasks.random.randint', return_value=5),
        patch('myapp.tasks.send_data_task.retry', side_effect=MaxRetriesExceededError),
        patch('myapp.tasks.time.sleep') as mock_sleep
    ):
        result = send_data_task(data={'key': 'value'})
        assert result == {"error": "Максимальное количество попыток превышено"}


@pytest.mark.django_db
def test_delete_old_webhooks():
    old_webhook = WebhookFactory()
    new_webhook = WebhookFactory()
    old_webhook.created_at = timezone.now() - timedelta(hours=5)
    old_webhook.save()
    delete_old_webhooks()
    assert not Webhook.objects.filter(id=old_webhook.id).exists()
    assert Webhook.objects.filter(id=new_webhook.id).exists()
