from django.contrib import admin
from .models import Webhook


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ["data", "user", "created_at"]
    search_fields = ['user__username']
