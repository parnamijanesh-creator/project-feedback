"""URL configuration for Weekly Team Feedback Tool."""
from django.contrib import admin
from django.urls import include, path
from .views import health_check, home_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
    path("", home_view, name="home"),
    path("", include("apps.accounts.urls")),
    path("projects/", include("apps.projects.urls")),
    path("", include("apps.cycles.urls")),
]

