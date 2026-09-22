"""Automated tests for Projects and Team Membership Management (Issue #4)."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.projects.models import Project, ProjectMember

User = get_user_model()


class ProjectModelAndManagementTests(TestCase):
    """Test suite for Project creation, membership roles, and permission enforcement."""

    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user(
            username="owner_user", email="owner@example.com", password="Password123!"
        )
        self.member_user = User.objects.create_user(
            username="team_member", email="member@example.com", password="Password123!"
        )
        self.outsider_user = User.objects.create_user(
            username="outsider", email="outsider@example.com", password="Password123!"
        )
        self.new_user = User.objects.create_user(
            username="candidate", email="candidate@example.com", password="Password123!"
        )

        # Baseline project with creator as facilitator and member_user as member
        self.project = Project.objects.create(
            name="Feedback Alpha",
            description="Alpha testing team feedback",
            created_by=self.creator,
        )
        self.creator_membership = ProjectMember.objects.create(
            project=self.project,
            user=self.creator,
            role=ProjectMember.Role.FACILITATOR,
        )
        self.member_membership = ProjectMember.objects.create(
            project=self.project,
            user=self.member_user,
            role=ProjectMember.Role.MEMBER,
        )

        self.list_url = reverse("project_list")
        self.create_url = reverse("project_create")
        self.detail_url = reverse("project_detail", kwargs={"slug": self.project.slug})

    def test_project_model_and_automatic_slug_generation(self):
        """Verify project attributes and automatic slug collision handling."""
        p1 = Project.objects.create(name="Design Systems", created_by=self.creator)
        self.assertEqual(p1.slug, "design-systems")

        # Duplicate name should generate distinct slug
        p2 = Project.objects.create(name="Design Systems", created_by=self.creator)
        self.assertEqual(p2.slug, "design-systems-1")
        self.assertNotEqual(p1.slug, p2.slug)

    def test_project_member_unique_together_constraint(self):
        """Verify that a user cannot have duplicate memberships in the same project."""
        with self.assertRaises(Exception):
            ProjectMember.objects.create(
                project=self.project,
                user=self.creator,
                role=ProjectMember.Role.MEMBER,
            )

    def test_project_creation_view_assigns_facilitator(self):
        """Creating a new project via web form assigns creator as FACILITATOR."""
        self.client.login(username="owner_user", password="Password123!")
        post_data = {
            "name": "Beta Sprint Team",
            "description": "Weekly retrospective for beta team",
        }
        response = self.client.post(self.create_url, data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        new_project = Project.objects.filter(name="Beta Sprint Team").first()
        self.assertIsNotNone(new_project)
        self.assertRedirects(response, reverse("project_detail", kwargs={"slug": new_project.slug}))

        membership = ProjectMember.objects.filter(project=new_project, user=self.creator).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, ProjectMember.Role.FACILITATOR)

    def test_project_list_displays_memberships_and_roles(self):
        """Project list displays only projects where user is member, along with their role."""
        self.client.login(username="team_member", password="Password123!")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feedback Alpha")
        self.assertContains(response, "Member")

        # Outsider visiting project list sees no projects
        self.client.login(username="outsider", password="Password123!")
        response_outsider = self.client.get(self.list_url)
        self.assertEqual(response_outsider.status_code, 200)
        self.assertNotContains(response_outsider, "Feedback Alpha")
        self.assertContains(response_outsider, "No projects yet")

    def test_project_detail_view_accessible_to_members(self):
        """Active members can view project overview and member roster."""
        self.client.login(username="team_member", password="Password123!")
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feedback Alpha")
        self.assertContains(response, "owner_user")
        self.assertContains(response, "team_member")
        # Regular members cannot see Add Member form
        self.assertNotContains(response, 'action="/projects/feedback-alpha/"')

    def test_project_detail_forbidden_for_non_members(self):
        """Non-members attempting to access project detail receive HTTP 403 Forbidden."""
        self.client.login(username="outsider", password="Password123!")
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 403)

    def test_facilitator_can_view_and_submit_add_member_form(self):
        """Facilitator sees Add Member form and can add registered user by username or email."""
        self.client.login(username="owner_user", password="Password123!")
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add Member")

        # Add candidate user by username as MEMBER
        post_data = {
            "identifier": "candidate",
            "role": ProjectMember.Role.MEMBER,
        }
        add_response = self.client.post(self.detail_url, data=post_data, follow=True)
        self.assertRedirects(add_response, self.detail_url)

        added_membership = ProjectMember.objects.filter(
            project=self.project, user=self.new_user
        ).first()
        self.assertIsNotNone(added_membership)
        self.assertEqual(added_membership.role, ProjectMember.Role.MEMBER)

    def test_add_member_by_email_and_duplicate_prevention(self):
        """Adding member by email succeeds; attempting to add existing member shows inline error."""
        self.client.login(username="owner_user", password="Password123!")

        # Add new user by email
        post_data = {
            "identifier": "candidate@example.com",
            "role": ProjectMember.Role.MEMBER,
        }
        response = self.client.post(self.detail_url, data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ProjectMember.objects.filter(project=self.project, user=self.new_user).exists()
        )

        # Attempting duplicate addition
        dup_response = self.client.post(self.detail_url, data=post_data)
        self.assertEqual(dup_response.status_code, 200)
        self.assertContains(dup_response, "User is already a member of this project")

    def test_add_member_nonexistent_user_error(self):
        """Adding a non-existent user email displays inline error: 'User not found'."""
        self.client.login(username="owner_user", password="Password123!")
        post_data = {
            "identifier": "unknown_ghost@example.com",
            "role": ProjectMember.Role.MEMBER,
        }
        response = self.client.post(self.detail_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User not found")

    def test_non_facilitator_cannot_add_members(self):
        """Member (non-facilitator) attempting to POST to add member receives HTTP 403."""
        self.client.login(username="team_member", password="Password123!")
        post_data = {
            "identifier": "candidate",
            "role": ProjectMember.Role.MEMBER,
        }
        response = self.client.post(self.detail_url, data=post_data)
        self.assertEqual(response.status_code, 403)

    def test_facilitator_role_update_and_last_facilitator_protection(self):
        """Facilitator can update roles, but cannot demote the only remaining Facilitator."""
        self.client.login(username="owner_user", password="Password123!")
        update_member_url = reverse(
            "update_member_role",
            kwargs={"slug": self.project.slug, "member_id": self.member_membership.id},
        )

        # Promote member_user to FACILITATOR
        resp = self.client.post(
            update_member_url, data={"role": ProjectMember.Role.FACILITATOR}, follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, ProjectMember.Role.FACILITATOR)

        # Now there are 2 facilitators; demote owner_user to MEMBER
        update_owner_url = reverse(
            "update_member_role",
            kwargs={"slug": self.project.slug, "member_id": self.creator_membership.id},
        )
        resp2 = self.client.post(
            update_owner_url, data={"role": ProjectMember.Role.MEMBER}, follow=True
        )
        self.assertEqual(resp2.status_code, 200)
        self.creator_membership.refresh_from_db()
        self.assertEqual(self.creator_membership.role, ProjectMember.Role.MEMBER)

        # Now only member_user is facilitator; log in as member_user and attempt to demote last facilitator
        self.client.login(username="team_member", password="Password123!")
        resp3 = self.client.post(
            update_member_url, data={"role": ProjectMember.Role.MEMBER}, follow=True
        )
        self.assertEqual(resp3.status_code, 200)
        self.assertContains(resp3, "A project must retain at least one Facilitator.")
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, ProjectMember.Role.FACILITATOR)
