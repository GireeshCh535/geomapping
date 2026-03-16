"""
API key authentication for geo_mapping API.
All API requests (except webhooks) require a valid API key when any active ApiKey exists in the DB.
Keys are created in Django admin; the plain key is shown once on creation.
"""
import hashlib

from django.conf import settings
from django.utils import timezone
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiKey


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Authenticate by X-API-Key header or Authorization: Api-Key <key>.
    Validates against ApiKey model (key_hash). If no active keys exist in DB, access is allowed.
    Webhooks are exempted by AllowIfWebhookOrHasAPIKey permission.
    """
    keyword = 'Api-Key'

    def authenticate(self, request):
        # If any active API key exists in DB, require a valid key
        has_active_keys = ApiKey.objects.filter(is_active=True).exists()
        if not has_active_keys:
            return (None, {'api_key': 'none'})

        provided = request.headers.get('X-API-Key') or request.META.get('HTTP_X_API_KEY')
        if not provided and request.headers.get('Authorization'):
            auth = request.headers.get('Authorization', '')
            if auth.startswith(f'{self.keyword} '):
                provided = auth[len(self.keyword):].strip()

        if not provided:
            raise AuthenticationFailed(
                'Missing API key. Provide X-API-Key header or Authorization: Api-Key <key>. '
                'Create and copy keys from Django admin → API Keys.'
            )

        key_hash = hashlib.sha256(provided.encode()).hexdigest()
        api_key_obj = ApiKey.objects.filter(key_hash=key_hash, is_active=True).first()
        if not api_key_obj:
            raise AuthenticationFailed('Invalid API key.')

        ApiKey.objects.filter(pk=api_key_obj.pk).update(last_used_at=timezone.now())
        return (None, {'api_key': 'valid'})

