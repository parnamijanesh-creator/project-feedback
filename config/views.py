from django.http import JsonResponse
from django.shortcuts import render


def health_check(request):
    """Simple health-check endpoint returning 200 OK status."""
    return JsonResponse({"status": "healthy"})


def home_view(request):
    """Home view rendering user dashboard or public landing page."""
    return render(request, "home.html")

