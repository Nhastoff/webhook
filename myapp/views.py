from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from keycloak import KeycloakOpenID
from rest_framework import status, views, permissions
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.response import Response

from .models import Webhook
from .serializers import WebhookSerializer
from .tasks import send_data_task


class WebhookCreateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WebhookSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WebhookWriteView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, webhook_id):
        try:
            Webhook.objects.get(id=webhook_id, user=request.user)
        except Webhook.DoesNotExist:
            return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)

        task = send_data_task.delay(request.data)
        return Response({'task_id': task.id}, status=status.HTTP_202_ACCEPTED)


class WebhookViewSet(ListAPIView):
    queryset = Webhook.objects.all()
    serializer_class = WebhookSerializer
    permission_classes = [permissions.IsAuthenticated]


class WebhookDetailView(RetrieveDestroyAPIView):
    queryset = Webhook.objects.all()
    serializer_class = WebhookSerializer
    permission_classes = [permissions.IsAuthenticated]


class TaskResultView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, task_id):
        result = send_data_task.AsyncResult(task_id)
        if result.ready():
            return Response({'result': result.get()}, status=status.HTTP_200_OK)
        return Response({'status': 'pending'}, status=status.HTTP_202_ACCEPTED)


def keycloak_login(request):
    redirect_uri = request.build_absolute_uri(reverse('keycloak_login'))
    code = request.GET.get('code')
    if code:
        keycloak_openid = KeycloakOpenID(server_url=settings.KEYCLOAK_SERVER_URL,
                                         client_id=settings.KEYCLOAK_CLIENT_ID,
                                         realm_name=settings.KEYCLOAK_REALM,
                                         client_secret_key=settings.KEYCLOAK_CLIENT_SECRET)

        token_response = keycloak_openid.token(grant_type='authorization_code', code=code,
                                               redirect_uri=request.build_absolute_uri(reverse('keycloak_login')))

        userinfo = keycloak_openid.userinfo(token_response['access_token'])

        username = userinfo.get('preferred_username')
        email = userinfo.get('email')
        full_name = userinfo.get('name')
        user, created = User.objects.get_or_create(username=username)

        if created or user.email != email or user.full_name != full_name:
            user.email = email
            user.full_name = full_name
            user.save()

        keycloak_roles = userinfo.get('roles', [])
        user.is_superuser = 'superuser' in keycloak_roles
        user.is_staff = 'staff' in keycloak_roles or user.is_superuser
        user.save()

        login(request, user)

        return redirect('/admin/')
    keycloak_login_url = f'{settings.KEYCLOAK_SERVER_URL}realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/auth?client_id={settings.KEYCLOAK_CLIENT_ID}&response_type=code&redirect_uri={redirect_uri}'
    return redirect(keycloak_login_url)


def admin_login_redirect(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return redirect(reverse('admin:index'))
        else:
            raise status.HTTP_403_FORBIDDEN("У вас нет доступа к этой странице.")
    else:
        return redirect('URL для логина через Keycloak')
