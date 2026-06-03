from django.http import JsonResponse


def health_check(request):
    """Lightweight liveness probe for ALB/ECS (no DB, cache, or auth)."""
    return JsonResponse({"status": "ok"})
