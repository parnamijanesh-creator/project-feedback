"""Core project-level views."""
from django.http import JsonResponse


def health_check(request):
    """Simple health-check endpoint returning 200 OK status."""
    return JsonResponse({"status": "healthy"})
