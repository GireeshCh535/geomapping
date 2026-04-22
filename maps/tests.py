from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from maps.authentication import APIKeyAuthentication


class APIKeyDomainRestrictionTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.auth = APIKeyAuthentication()

    def test_x_api_caller_host_matches_wildcard(self):
        request = self.factory.get(
            '/api/foo',
            HTTP_X_API_CALLER_HOST='prod-be-aws.1acre.in',
        )
        key = SimpleNamespace(allowed_domains=['*.1acre.in'])
        self.auth._validate_domain(request, key)

    def test_x_api_caller_host_rejected_when_not_whitelisted(self):
        request = self.factory.get(
            '/api/foo',
            HTTP_X_API_CALLER_HOST='evil.example.com',
        )
        key = SimpleNamespace(allowed_domains=['*.1acre.in'])
        with self.assertRaises(AuthenticationFailed):
            self.auth._validate_domain(request, key)

    def test_no_origin_referer_or_caller_header_raises(self):
        request = self.factory.get('/api/foo')
        key = SimpleNamespace(allowed_domains=['*.1acre.in'])
        with self.assertRaises(AuthenticationFailed):
            self.auth._validate_domain(request, key)

    @override_settings(API_KEY_DOMAIN_FALLBACK_HOST='prod-be-aws.1acre.in')
    def test_domain_fallback_host_matches_allowed_patterns(self):
        request = self.factory.get('/api/foo')
        key = SimpleNamespace(allowed_domains=['*.1acre.in'])
        self.auth._validate_domain(request, key)
