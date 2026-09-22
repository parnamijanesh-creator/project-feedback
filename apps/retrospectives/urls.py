"""URL configuration for Retrospective sessions and cluster management."""
from django.urls import path
from .views import (
    ClusterCreateView,
    ClusterDeleteView,
    ClusterTitleView,
    ClusterUpdateView,
    ClusterVoteCastView,
    ClusterVoteRetractView,
    RetroBoardView,
    RetroCardMoveView,
    RetroCloseVotingView,
    RetroRevealView,
    RetroRunClusteringView,
    RetroStageTransitionView,
    TopicNoteCreateView,
    TopicNoteDeleteView,
    TopicStatusUpdateView,
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
    path("projects/<slug:slug>/cycles/<int:pk>/retro/vote/close/", RetroCloseVotingView.as_view(), name="retro_close_voting"),
    path("retro/topics/<int:topic_id>/status/", TopicStatusUpdateView.as_view(), name="topic_status_update"),
    path("retro/topics/<int:topic_id>/notes/", TopicNoteCreateView.as_view(), name="topic_note_create"),
    path("retro/notes/<int:note_id>/delete/", TopicNoteDeleteView.as_view(), name="topic_note_delete"),
]


