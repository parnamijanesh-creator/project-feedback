"""URL configuration for Retrospective sessions."""
from django.urls import path
from .views import RetroBoardView, RetroRevealView

urlpatterns = [
    path("projects/<slug:slug>/cycles/<int:pk>/retro/", RetroBoardView.as_view(), name="retro_board"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/reveal/", RetroRevealView.as_view(), name="retro_reveal"),
]
