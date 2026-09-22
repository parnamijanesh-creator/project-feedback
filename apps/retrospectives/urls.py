"""URL configuration for Retrospective sessions and cluster management."""
from django.urls import path
from .views import (
    ClusterCreateView,
    ClusterDeleteView,
    ClusterTitleView,
    ClusterUpdateView,
    RetroBoardView,
    RetroRevealView,
    RetroRunClusteringView,
    RetroStageTransitionView,
    RetroCardMoveView,
    ClusterVoteCastView,
    ClusterVoteRetractView,
)

urlpatterns = [
    path("projects/<slug:slug>/cycles/<int:pk>/retro/", RetroBoardView.as_view(), name="retro_board"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/reveal/", RetroRevealView.as_view(), name="retro_reveal"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/stage/", RetroStageTransitionView.as_view(), name="retro_stage_transition"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/cluster/ai/", RetroRunClusteringView.as_view(), name="retro_run_clustering"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/clusters/", ClusterCreateView.as_view(), name="cluster_create"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/clusters/<int:cluster_id>/", ClusterUpdateView.as_view(), name="cluster_update"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/clusters/<int:cluster_id>/title/", ClusterTitleView.as_view(), name="cluster_title"),
    path("projects/<slug:slug>/cycles/<int:pk>/retro/clusters/<int:cluster_id>/delete/", ClusterDeleteView.as_view(), name="cluster_delete"),
    path("retro/cards/<int:card_id>/move/", RetroCardMoveView.as_view(), name="retro_card_move"),
    path("retro/clusters/<int:cluster_id>/vote/", ClusterVoteCastView.as_view(), name="cluster_vote_cast"),
    path("retro/clusters/<int:cluster_id>/retract/", ClusterVoteRetractView.as_view(), name="cluster_vote_retract"),
]
