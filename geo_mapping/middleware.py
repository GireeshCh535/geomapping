"""
Middleware to restrict API access to requests from allowed frontend origins.

- Requests with Origin/Referer from an allowed origin are accepted.
- Requests with no Origin/Referer (e.g. Postman, curl, server-to-server) are allowed
  so webhooks and tools keep working.
- Requests with Origin/Referer from a different origin are rejected (403).

This complements CORS: CORS blocks cross-origin browser requests; this middleware
rejects API requests that explicitly come from a non-allowed origin when the
client sends Origin/Referer (e.g. browser from another site).
"""
from urllib.parse import urlparse

from django.conf import settings
from django.http import JsonResponse


# API path prefix; only these requests are checked
API_PATH_PREFIX = "/api/"

# Paths that are server-to-server (webhooks, callbacks, build) or public (tiles) and skip origin check
API_SKIP_ORIGIN_CHECK_PREFIXES = (
    "/api/webhooks/",
    "/api/tiles/land-plot-mvt-build/",
    "/api/tiles/",  # Tile GET requests (MVT/PNG) are public; allow from any origin
)


def _get_origin_from_referer(referer: str) -> str | None:
    """Return scheme + netloc (e.g. https://layers.1acre.in) from Referer URL."""
    try:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return None


def _origin_allowed(origin: str) -> bool:
    allowed = getattr(settings, "CORS_ALLOWED_ORIGINS", None) or []
    return origin.rstrip("/") in [o.rstrip("/") for o in allowed]


class RestrictAPIOriginMiddleware:
    """
    Reject /api/ requests (except webhooks) when Origin or Referer is present
    and not in CORS_ALLOWED_ORIGINS. Requests without Origin/Referer are allowed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow disabling origin check via env (e.g. tests, internal tools)
        if getattr(settings, "RESTRICT_API_ORIGIN", True) is False:
            return self.get_response(request)
        if not request.path.startswith(API_PATH_PREFIX):
            return self.get_response(request)
        for prefix in API_SKIP_ORIGIN_CHECK_PREFIXES:
            if request.path.startswith(prefix):
                return self.get_response(request)

        origin = request.headers.get("Origin", "").strip()
        referer = request.headers.get("Referer", "").strip()

        # No origin or referer: allow (server-to-server, Postman, curl)
        if not origin and not referer:
            return self.get_response(request)

        if origin and _origin_allowed(origin):
            return self.get_response(request)
        if referer:
            ref_origin = _get_origin_from_referer(referer)
            if ref_origin and _origin_allowed(ref_origin):
                return self.get_response(request)

        return JsonResponse(
            {"detail": "Request origin not allowed."},
            status=403,
        )
