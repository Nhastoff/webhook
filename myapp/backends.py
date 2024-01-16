from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from keycloak import KeycloakOpenID
from django.contrib.auth import get_user_model


class KeycloakAuthenticationBackend(ModelBackend):
    def authenticate(self, request, **kwargs):
        if request.path.startswith('/admin/'):
            keycloak_openid = KeycloakOpenID(server_url=settings.KEYCLOAK_SERVER_URL,
                                             client_id=settings.KEYCLOAK_CLIENT_ID,
                                             realm_name=settings.KEYCLOAK_REALM,
                                             client_secret_key=settings.KEYCLOAK_CLIENT_SECRET)
            if not keycloak_openid.is_token_valid(request):
                return None

            user_info = keycloak_openid.userinfo(request)

            user_roles = keycloak_openid.user_roles(request)
            if 'admin' in user_roles:
                user_model = get_user_model()
                user = user_model.objects.get_or_create(username=user_info['email'], email=user_info['email'])
                return user

        return None

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            return user_model.objects.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
