import factory
from django.contrib.auth.models import User

from myapp.models import Webhook


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Faker('user_name')
    password = factory.PostGenerationMethodCall('set_password', 'defaultpassword')


class WebhookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Webhook

    user = factory.SubFactory(UserFactory)
    data = factory.Faker('pydict', value_types=[int, float, str, bool])
