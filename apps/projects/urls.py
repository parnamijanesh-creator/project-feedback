"""URL configuration for projects and team memberships."""
from django.urls import path
from .views import ProjectCreateView, ProjectDetailView, ProjectListView, update_member_role_view

urlpatterns = [
    path("", ProjectListView.as_view(), name="project_list"),
    path("new/", ProjectCreateView.as_view(), name="project_create"),
    path("<slug:slug>/", ProjectDetailView.as_view(), name="project_detail"),
    path("<slug:slug>/members/<int:member_id>/role/", update_member_role_view, name="update_member_role"),
]
