from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from keycloak import KeycloakOpenID
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Webhook
from .permission import PermIsAuthenticated
from .schemas import UserInfo
from .serializers import WebhookSerializer
from .tasks import send_data_task


class WebhookCreateView(PermIsAuthenticated, APIView):

    def post(self, request):
        serializer = WebhookSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)


class WebhookWriteView(PermIsAuthenticated, APIView):

    def post(self, request, webhook_id):
        try:
            Webhook.objects.get(id=webhook_id, user=request.user)
        except Webhook.DoesNotExist:
            return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)

        task = send_data_task.delay(request.data)
        return Response({'task_id': task.id}, status=status.HTTP_202_ACCEPTED)


class WebhookViewSet(PermIsAuthenticated, ListAPIView):
    queryset = Webhook.objects.all()
    serializer_class = WebhookSerializer


class WebhookDetailView(PermIsAuthenticated, RetrieveDestroyAPIView):
    queryset = Webhook.objects.all()
    serializer_class = WebhookSerializer


class TaskResultView(PermIsAuthenticated, APIView):

    def get(self, request, task_id):
        result = send_data_task.AsyncResult(task_id)
        if result.ready():
            return Response({'result': result.get()}, status=status.HTTP_200_OK)
        return Response({'status': 'pending'}, status=status.HTTP_202_ACCEPTED)


class KeycloakLoginView(View):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keycloak_openid = KeycloakOpenID(
            server_url=settings.KEYCLOAK_SERVER_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            realm_name=settings.KEYCLOAK_REALM,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET
        )

    def get(self, request, *args, **kwargs):
        redirect_uri = request.build_absolute_uri(reverse('keycloak_login'))
        code = request.GET.get('code')

        if code:
            try:
                token_response = self.keycloak_openid.token(
                    grant_type='authorization_code',
                    code=code,
                    redirect_uri=redirect_uri
                )

                user = self._get_or_create_user(self.keycloak_openid.userinfo(token_response['access_token']))

                login(request, user)

                return redirect('/admin/')
            except Exception as e:
                return HttpResponse("Authentication failed", status=401)

        keycloak_login_url = self.keycloak_openid.auth_url(redirect_uri=redirect_uri, scope="openid profile roles")
        return redirect(keycloak_login_url)

    def _get_or_create_user(self, user_info: dict) -> dict:
        changes_user = False
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
            changes_user = True

        keycloak_roles = userinfo.group or []
        if ('/superuser' in keycloak_roles != user.is_superuser) or (
                '/staff' in keycloak_roles != user.is_staff
        ) or (user.is_superuser != user.is_staff):
            user.is_superuser = '/superuser' in keycloak_roles
            user.is_staff = '/staff' in keycloak_roles or user.is_superuser
            changes_user = True

        if changes_user:
            user.save()

        user.refresh_from_db()

        return user
