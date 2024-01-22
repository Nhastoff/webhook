from rest_framework import permissions


class PermIsAuthenticated:
    permission_classes = [permissions.IsAuthenticated]
