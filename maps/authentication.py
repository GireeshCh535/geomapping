"""
API key authentication for geo_mapping API.
All API requests (except webhooks) require a valid API key via header when API_KEY is set.
"""
from django.conf import settings
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Authenticate by X-API-Key header or Authorization: Api-Key <key>.
    When settings.API_KEY is set, requests must include a matching key (webhooks exempted by permission).
    When API_KEY is empty, all requests are allowed (auth not enforced).
    """
    keyword = 'Api-Key'

    def authenticate(self, request):
        api_key = getattr(settings, 'API_KEY', None) or ''
        if not api_key:
            return (None, {'api_key': 'none'})

        provided = request.headers.get('X-API-Key') or request.META.get('HTTP_X_API_KEY')
        if not provided and request.headers.get('Authorization'):
            auth = request.headers.get('Authorization', '')
            if auth.startswith(f'{self.keyword} '):
                provided = auth[len(self.keyword):].strip()

        if not provided:
            raise AuthenticationFailed('Missing or invalid API key. Provide X-API-Key header or Authorization: Api-Key <key>.')
        if provided != api_key:
            raise AuthenticationFailed('Invalid API key.')
        return (None, {'api_key': 'valid'})
