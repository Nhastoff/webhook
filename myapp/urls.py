from myapp.views import TaskResultView, WebhookWriteView, WebhookCreateView, WebhookViewSet, \
    WebhookDetailView
from django.urls import path

urlpatterns = [
    path('webhook/', WebhookCreateView.as_view(), name='create-webhook'),
    path('webhook/<int:webhook_id>/write/', WebhookWriteView.as_view(), name='write-webhook'),
    path('webhook/list/', WebhookViewSet.as_view(), name="webhook-list"),
    path('webhook/<int:pk>/', WebhookDetailView.as_view(), name="webhook-detail"),

    path('task/<str:task_id>/', TaskResultView.as_view(), name='task-result'),
]
