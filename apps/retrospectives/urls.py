"""URL configuration for Retrospective sessions."""
from django.urls import path
from .views import RetroBoardView, RetroRevealView, RetroRunClusteringView

urlpatterns = [
    path("projects/<slug:slug>/cycles/<int:pk>/retro/", RetroBoardView.as_view(), name="retro_board"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/reveal/", RetroRevealView.as_view(), name="retro_reveal"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/cluster/ai/", RetroRunClusteringView.as_view(), name="retro_run_clustering"),
]
