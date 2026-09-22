"""URL configuration for Weekly Team Feedback Tool."""
from django.contrib import admin
from django.urls import path
from .views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
]
