"""
API key authentication for geo_mapping API.
All API requests (except webhooks) require a valid API key when any active ApiKey exists in the DB.
Keys are created in Django admin; the plain key is shown once on creation.
If a key has allowed_domains set, the caller host must match one of those domains.
That host is taken from Origin, Referer, or (for server-to-server clients that send neither)
the optional X-API-Caller-Host header with a bare hostname, e.g. prod-be-aws.1acre.in.
"""
import hashlib
from urllib.parse import urlparse

from django.utils import timezone
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiKey


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Authenticate by X-API-Key header or Authorization: Api-Key <key>.
    Validates against ApiKey model (key_hash). If no active keys exist in DB, access is allowed.
    If the matched key has allowed_domains set, the caller host (Origin / Referer /
    X-API-Caller-Host) is also validated.
    Webhooks are exempted by AllowIfWebhookOrHasAPIKey permission.
    """
    keyword = 'Api-Key'

    def authenticate(self, request):
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

        self._validate_domain(request, api_key_obj)

        ApiKey.objects.filter(pk=api_key_obj.pk).update(last_used_at=timezone.now())
        return (None, {'api_key': 'valid'})

    def _validate_domain(self, request, api_key_obj):
        """If the key has allowed_domains, ensure the caller host matches an allowed pattern."""
        allowed_domains = api_key_obj.allowed_domains
        if not allowed_domains:
            return

        origin = request.headers.get('Origin', '')
        referer = request.headers.get('Referer', '') or request.META.get('HTTP_REFERER', '')
        caller_host_raw = (
            request.headers.get('X-API-Caller-Host', '')
            or request.META.get('HTTP_X_API_CALLER_HOST', '')
        )

        request_host = None
        for header in (origin, referer):
            if header:
                parsed = urlparse(header)
                if parsed.hostname:
                    request_host = parsed.hostname.lower()
                    break

        if not request_host and caller_host_raw.strip():
            request_host = self._hostname_from_caller_header(caller_host_raw.strip())

        if not request_host:
            raise AuthenticationFailed(
                'This API key is domain-restricted. Browser clients must send Origin or Referer '
                'from an allowed domain. Server-to-server clients must send '
                'X-API-Caller-Host with the caller hostname (e.g. prod-be-aws.1acre.in).'
            )

        normalized = [d.lower().strip() for d in allowed_domains]
        if any(self._domain_matches(request_host, d) for d in normalized):
            return

        raise AuthenticationFailed(
            f'This API key is not authorized for domain "{request_host}". '
            'Contact the API owner to whitelist your domain.'
        )

    @staticmethod
    def _hostname_from_caller_header(raw: str) -> str | None:
        """Normalize X-API-Caller-Host to a lowercase hostname."""
        if '://' in raw:
            parsed = urlparse(raw)
            return parsed.hostname.lower() if parsed.hostname else None
        # bare hostname; ignore accidental path or port
        host = raw.split('/')[0].split(':')[0].strip().lower()
        return host or None

    @staticmethod
    def _domain_matches(host: str, pattern: str) -> bool:
        """
        Match a hostname against a domain pattern.

        Supported patterns:
          *.1acre.in   → any single subdomain: layers.1acre.in, app.1acre.in
                         does NOT match bare 1acre.in
          1acre.in     → exact match only: 1acre.in
                         does NOT auto-match subdomains (use *.1acre.in for that)
          layers.1acre.in → exact match only
        """
        if pattern.startswith('*.'):
            # Wildcard: match any single-level subdomain of the base domain
            base = pattern[2:]  # strip leading "*."
            return host.endswith('.' + base) and host != base
        else:
            return host == pattern
