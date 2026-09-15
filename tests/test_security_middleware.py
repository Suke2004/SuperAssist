"""Unit tests for Phase 1 security middleware, token enforcement, and DNS rebinding protection."""

import pytest
from fastapi.testclient import TestClient
from main import app
from core.config import APP_SESSION_TOKEN


@pytest.fixture
def client():
    return TestClient(app)


class TestSecurityMiddleware:
    def test_root_index_injects_token(self, client):
        """GET / should serve HTML with injected app session token."""
        response = client.get("/")
        assert response.status_code == 200
        assert f'content="{APP_SESSION_TOKEN}"' in response.text
        assert f'window.__APP_TOKEN__ = "{APP_SESSION_TOKEN}"' in response.text

    def test_public_diagnostic_endpoints_exempt(self, client):
        """Diagnostic / setup endpoints do not require token."""
        res_health = client.get("/api/health")
        assert res_health.status_code == 200

        res_metrics = client.get("/api/metrics")
        assert res_metrics.status_code == 200

        res_config = client.get("/api/config")
        assert res_config.status_code == 200

    def test_protected_endpoint_rejected_without_token(self, client):
        """Sensitive endpoints like /api/ai-providers/full reject requests lacking token."""
        response = client.get("/api/ai-providers/full")
        assert response.status_code == 403
        assert "Missing or invalid application token" in response.json()["detail"]

    def test_protected_endpoint_rejected_with_invalid_token(self, client):
        """Requests with bogus token are rejected."""
        response = client.get("/api/ai-providers/full", headers={"X-App-Token": "invalid_fake_token"})
        assert response.status_code == 403
        assert "Missing or invalid application token" in response.json()["detail"]

    def test_protected_endpoint_allowed_with_valid_token(self, client):
        """Requests with valid X-App-Token succeed."""
        response = client.get("/api/ai-providers/full", headers={"X-App-Token": APP_SESSION_TOKEN})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_foreign_origin_rejected(self, client):
        """Browser requests from foreign origins are rejected."""
        response = client.get(
            "/api/ai-providers/full",
            headers={
                "X-App-Token": APP_SESSION_TOKEN,
                "Origin": "https://malicious-website.com"
            }
        )
        assert response.status_code == 403
        assert "Cross-origin request rejected" in response.json()["detail"]

    def test_dns_rebinding_rejected(self, client):
        """Requests with external Host headers are blocked."""
        response = client.get(
            "/api/health",
            headers={"Host": "evil-attacker.com:8002"}
        )
        assert response.status_code == 403
        assert "Invalid Host header" in response.json()["detail"]

    def test_cross_site_sec_fetch_rejected(self, client):
        """Requests marked as cross-site by browser are rejected."""
        response = client.get(
            "/api/ai-providers/full",
            headers={
                "X-App-Token": APP_SESSION_TOKEN,
                "Sec-Fetch-Site": "cross-site"
            }
        )
        assert response.status_code == 403
        assert "Cross-site request rejected" in response.json()["detail"]
