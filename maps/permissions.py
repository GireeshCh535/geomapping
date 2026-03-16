"""
Custom permissions for geo_mapping API.
Webhook paths are always allowed; all other API requests require API key when API_KEY is set.
"""
from rest_framework import permissions


class AllowIfWebhookOrHasAPIKey(permissions.BasePermission):
    """
    Allow request if:
    - path contains 'webhooks/' (webhook endpoints), or
    - request was authenticated (e.g. valid API key), or
    - API_KEY is not set (auth not enforced).
    """
    def has_permission(self, request, view):
        if 'webhooks/' in (request.path or ''):
            return True
        # Authenticated by APIKeyAuthentication (request.auth set) or API_KEY empty
        if request.auth:
            return True
        # API key required but not provided
        from django.conf import settings
        if getattr(settings, 'API_KEY', None):
            return False
        return True
