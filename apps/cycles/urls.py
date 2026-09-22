"""URL configuration for feedback cycles."""
from django.urls import path
from .views import CycleCreateView, CycleDetailView, CycleStatusTransitionView

urlpatterns = [
    path("projects/<slug:slug>/cycles/new/", CycleCreateView.as_view(), name="cycle_create"),
    path("projects/<slug:slug>/cycles/<int:pk>/", CycleDetailView.as_view(), name="cycle_detail"),
    path("projects/<slug:slug>/cycles/<int:pk>/status/", CycleStatusTransitionView.as_view(), name="cycle_status_transition"),
]
