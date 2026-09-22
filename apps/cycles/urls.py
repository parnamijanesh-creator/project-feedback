"""URL configuration for feedback cycles and card submissions."""
from django.urls import path
from .views import (
    CardDeleteView,
    CardDetailPartialView,
    CardEditView,
    CycleCreateView,
    CycleDetailView,
    CycleStatusTransitionView,
    FeedbackSubmitView,
)

urlpatterns = [
    path("projects/<slug:slug>/cycles/new/", CycleCreateView.as_view(), name="cycle_create"),
    path("projects/<slug:slug>/cycles/<int:pk>/", CycleDetailView.as_view(), name="cycle_detail"),
    path("projects/<slug:slug>/cycles/<int:pk>/status/", CycleStatusTransitionView.as_view(), name="cycle_status_transition"),
    path("projects/<slug:slug>/cycles/<int:pk>/submit/", FeedbackSubmitView.as_view(), name="feedback_submit"),
    path("projects/<slug:slug>/cycles/<int:cycle_pk>/cards/<int:card_pk>/edit/", CardEditView.as_view(), name="card_edit"),
    path("projects/<slug:slug>/cycles/<int:cycle_pk>/cards/<int:card_pk>/", CardDetailPartialView.as_view(), name="card_detail_partial"),
    path("projects/<slug:slug>/cycles/<int:cycle_pk>/cards/<int:card_pk>/delete/", CardDeleteView.as_view(), name="card_delete"),
]
