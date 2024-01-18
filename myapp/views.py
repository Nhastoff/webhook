from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.urls import reverse
from keycloak import KeycloakOpenID
from rest_framework import status, permissions
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Webhook
from .schemas import UserInfo
from .serializers import WebhookSerializer
from .tasks import send_data_task


class WebhookCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WebhookSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WebhookWriteView(APIView):
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


class TaskResultView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, task_id):
        result = send_data_task.AsyncResult(task_id)
        if result.ready():
            return Response({'result': result.get()}, status=status.HTTP_200_OK)
        return Response({'status': 'pending'}, status=status.HTTP_202_ACCEPTED)


def get_or_create_user(user_info: dict) -> dict:
    userinfo = UserInfo(**user_info)

    username = userinfo.preferred_username
    email = userinfo.email
    first_name = userinfo.given_name
    last_name = userinfo.family_name
    user, created = User.objects.get_or_create(username=username)

    if created or user.email != email or user.first_name != first_name or user.last_name != last_name:
        user.email = email
        user.first_name = first_name
        user.last_name = last_name

    keycloak_roles = userinfo.groups or []
    user.is_superuser = 'superuser' in keycloak_roles
    user.is_staff = 'staff' in keycloak_roles or user.is_superuser
    user.save()

    user, _ = User.objects.get_or_create(username=username)

    return user


def keycloak_login(request):
    redirect_uri = request.build_absolute_uri(reverse('keycloak_login'))
    code = request.GET.get('code')
    keycloak_openid = KeycloakOpenID(server_url=settings.KEYCLOAK_SERVER_URL,
                                     client_id=settings.KEYCLOAK_CLIENT_ID,
                                     realm_name=settings.KEYCLOAK_REALM,
                                     client_secret_key=settings.KEYCLOAK_CLIENT_SECRET)
    if code:
        try:
            token_response = keycloak_openid.token(grant_type='authorization_code', code=code,
                                                   redirect_uri=redirect_uri)

            user = get_or_create_user(keycloak_openid.userinfo(token_response['access_token']))

            login(request, user)

            return redirect('/admin/')
        except Exception as e:
            print(f"Error during Keycloak authentication: {e}")
    keycloak_login_url = keycloak_openid.auth_url(redirect_uri=redirect_uri, scope="openid profile roles")
    return redirect(keycloak_login_url)
