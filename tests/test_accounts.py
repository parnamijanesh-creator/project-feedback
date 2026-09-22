"""Unit and integration tests for accounts, authentication, and session management."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class UserAuthenticationTests(TestCase):
    """Test suite covering registration, login, logout, and session workflows."""

    def setUp(self):
        self.client = Client()
        self.register_url = reverse("register")
        self.login_url = reverse("login")
        self.logout_url = reverse("logout")
        self.home_url = reverse("home")

        self.valid_user_data = {
            "username": "testdeveloper",
            "email": "developer@example.com",
            "password1": "ComplexP@ssw0rd!2026",
            "password2": "ComplexP@ssw0rd!2026",
        }

    def test_custom_user_model_configured(self):
        """Verify the custom User model is configured with unique email."""
        self.assertEqual(User._meta.app_label, "accounts")
        self.assertEqual(User._meta.model_name, "user")
        email_field = User._meta.get_field("email")
        self.assertTrue(email_field.unique)

    def test_register_page_renders_form(self):
        """Verify /register/ renders form with username, email, and password fields."""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')
        self.assertContains(response, "Create your account")

    def test_successful_registration(self):
        """Submitting valid credentials creates user, hashes password, logs in, and redirects."""
        response = self.client.post(self.register_url, data=self.valid_user_data, follow=True)
        self.assertRedirects(response, self.home_url)

        user = User.objects.filter(username="testdeveloper").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "developer@example.com")
        self.assertTrue(user.check_password("ComplexP@ssw0rd!2026"))

        # Verify authenticated session
        self.assertEqual(int(self.client.session.get("_auth_user_id")), user.pk)
        self.assertContains(response, "Hello, <span class=\"font-semibold text-slate-900\">testdeveloper</span>")

    def test_duplicate_username_prevented(self):
        """Registering with an existing username displays error and prevents duplicate."""
        User.objects.create_user(
            username="testdeveloper", email="other@example.com", password="ComplexP@ssw0rd!2026"
        )
        response = self.client.post(self.register_url, data=self.valid_user_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "username", "A user with this username already exists.")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_email_prevented(self):
        """Registering with an existing email displays error and prevents duplicate."""
        User.objects.create_user(
            username="existinguser", email="developer@example.com", password="ComplexP@ssw0rd!2026"
        )
        response = self.client.post(self.register_url, data=self.valid_user_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email", "A user with this email already exists.")
        self.assertEqual(User.objects.count(), 1)

    def test_weak_password_validation(self):
        """Weak passwords trigger validation errors and preserve username/email fields."""
        weak_data = {
            "username": "weakpwduser",
            "email": "weak@example.com",
            "password1": "12345",
            "password2": "12345",
        }
        response = self.client.post(self.register_url, data=weak_data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="weakpwduser").exists())
        # Check that valid field values are preserved in form
        self.assertContains(response, 'value="weakpwduser"')
        self.assertContains(response, 'value="weak@example.com"')
        # Form should have errors on password
        form = response.context["form"]
        self.assertTrue(form.errors.get("password2"))
        self.assertIn("This password is too short.", str(form.errors.get("password2")))

    def test_login_page_renders_form(self):
        """Verify /login/ renders credentials form with Tailwind styling."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, "Sign in to your account")

    def test_login_with_invalid_credentials(self):
        """Invalid credentials show error and do not authenticate session."""
        response = self.client.post(
            self.login_url,
            data={"username": "nonexistent", "password": "WrongPassword123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_successful_login_and_safe_redirect(self):
        """Valid login authenticates user and safely redirects to internal next URL."""
        user = User.objects.create_user(
            username="alice", email="alice@example.com", password="SecretAlicePassword1!"
        )
        response = self.client.post(
            f"{self.login_url}?next=/health/",
            data={"username": "alice", "password": "SecretAlicePassword1!"},
            follow=True,
        )
        self.assertRedirects(response, "/health/")
        self.assertEqual(int(self.client.session.get("_auth_user_id")), user.pk)

    def test_login_rejects_open_redirect(self):
        """Login ignores untrusted external next URL and falls back to default redirect URL."""
        User.objects.create_user(
            username="bob", email="bob@example.com", password="SecretBobPassword1!"
        )
        response = self.client.post(
            f"{self.login_url}?next=https://malicious-site.com/steal-data",
            data={"username": "bob", "password": "SecretBobPassword1!"},
            follow=True,
        )
        self.assertRedirects(response, self.home_url)

    def test_logout_terminates_session(self):
        """POST to /logout/ clears session and redirects to /login/."""
        User.objects.create_user(
            username="charlie", email="charlie@example.com", password="SecretCharliePassword1!"
        )
        self.client.login(username="charlie", password="SecretCharliePassword1!")
        self.assertIn("_auth_user_id", self.client.session)

        response = self.client.post(self.logout_url, follow=True)
        self.assertRedirects(response, self.login_url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_user_redirected_from_login_and_register(self):
        """Already authenticated users visiting /login/ or /register/ are redirected to home."""
        User.objects.create_user(
            username="david", email="david@example.com", password="SecretDavidPassword1!"
        )
        self.client.login(username="david", password="SecretDavidPassword1!")

        login_response = self.client.get(self.login_url)
        self.assertRedirects(login_response, self.home_url)

        register_response = self.client.get(self.register_url)
        self.assertRedirects(register_response, self.home_url)

    def test_base_layout_navigation_links(self):
        """Base layout renders Login/Register when anonymous, and user info/Logout when authenticated."""
        # Anonymous state
        anon_resp = self.client.get(self.home_url)
        self.assertContains(anon_resp, 'href="/login/"')
        self.assertContains(anon_resp, 'href="/register/"')
        self.assertNotContains(anon_resp, 'action="/logout/"')

        # Authenticated state
        User.objects.create_user(
            username="emma", email="emma@example.com", password="SecretEmmaPassword1!"
        )
        self.client.login(username="emma", password="SecretEmmaPassword1!")

        auth_resp = self.client.get(self.home_url)
        self.assertContains(auth_resp, "Hello,")
        self.assertContains(auth_resp, "emma")
        self.assertContains(auth_resp, 'action="/logout/"')
        self.assertNotContains(auth_resp, 'href="/login/"')
