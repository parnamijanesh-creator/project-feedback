"""Smoke tests verifying test runner and baseline health-check endpoint."""
from django.test import SimpleTestCase, TestCase, Client
from django.urls import reverse
from django.db import connection


class SmokeTest(SimpleTestCase):
    """Smoke test suite to ensure the test runner and health check function properly."""

    def setUp(self):
        self.client = Client()

    def test_runner_is_functional(self):
        """Verify the test execution framework operates correctly."""
        self.assertTrue(True)

    def test_health_check_endpoint_returns_200(self):
        """Verify the health-check endpoint returns HTTP 200 OK."""
        response = self.client.get(reverse("health_check"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/json")
        self.assertEqual(response.json(), {"status": "healthy"})

    def test_health_check_direct_path(self):
        """Verify the health-check endpoint is accessible at /health/."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})


class DatabaseSmokeTest(TestCase):
    """Verify database connectivity and query execution against active database."""

    def test_database_connection_and_backend(self):
        """Verify database connection can execute SQL and query engine."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            self.assertEqual(row[0], 1)
