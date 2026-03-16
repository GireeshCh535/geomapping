"""
Custom permissions for geo_mapping API.
Webhook paths are always allowed; all other API requests require valid API key when any active ApiKey exists in DB.
"""
from rest_framework import permissions


class AllowIfWebhookOrHasAPIKey(permissions.BasePermission):
    """
    Allow request if:
    - path contains 'webhooks/' (webhook endpoints), or
    - request was authenticated (valid API key from ApiKey model, or no keys in DB).
    """
    def has_permission(self, request, view):
        if 'webhooks/' in (request.path or ''):
            return True
        if request.auth:
            return True
        return False
