from django.contrib.auth.models import User
from django.db import models


class Webhook(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()

    def __str__(self):
        return f"Webhook {self.id} by {self.user}"
