from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from maps.authentication import APIKeyAuthentication, path_disallows_api_key_domain_fallback


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
        # Non-strict path: fallback allowed (e.g. developer-listings map-data)
        request = self.factory.get('/api/developer-listings/developerplot/1/map-data/')
        key = SimpleNamespace(allowed_domains=['*.1acre.in'])
        self.auth._validate_domain(request, key)

    @override_settings(API_KEY_DOMAIN_FALLBACK_HOST='prod-be-aws.1acre.in')
    def test_strict_path_ignores_domain_fallback(self):
        request = self.factory.get('/api/layers/nearby/')
        key = SimpleNamespace(allowed_domains=['*.1acre.in'])
        with self.assertRaises(AuthenticationFailed):
            self.auth._validate_domain(request, key)

    def test_strict_paths_root_mount(self):
        req = self.factory.get('/layers/telangana/hyderabad/foo/bounds/')
        self.assertTrue(path_disallows_api_key_domain_fallback(req))

    def test_non_strict_developer_listings(self):
        req = self.factory.get('/api/developer-listings/')
        self.assertFalse(path_disallows_api_key_domain_fallback(req))

