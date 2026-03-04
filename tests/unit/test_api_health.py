"""Tests for Phase F3 — FastAPI Skeleton & Health Endpoints.

Covers: app factory, health endpoints, response envelope, request ID,
error handling, OpenAPI generation, API versioning.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import ASGITransport


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test."""
    from noa.api.app import create_app

    return create_app()


@pytest.fixture
async def client(app):
    """Async test client using httpx + ASGITransport."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c


# --- App Factory ---


@pytest.mark.f3
class TestAppFactory:
    """Test FastAPI application factory."""

    def test_create_app_returns_fastapi(self, app):
        from fastapi import FastAPI

        assert isinstance(app, FastAPI)

    def test_app_has_title(self, app):
        assert app.title == "Noa"

    def test_openapi_url_is_set(self, app):
        assert app.openapi_url is not None


# --- Health Endpoints ---


@pytest.mark.f3
class TestHealthEndpoints:
    """Test health endpoints per SPEC.md §28.5."""

    async def test_liveness_returns_200(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_liveness_response_envelope(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        body = resp.json()
        assert body["ok"] is True
        assert "data" in body
        assert body["data"]["status"] == "alive"
        assert body["error"] is None
        assert "trace_id" in body

    async def test_readiness_returns_200(self, client: httpx.AsyncClient):
        resp = await client.get("/health/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["status"] in ("ready", "degraded")

    async def test_metrics_returns_200(self, client: httpx.AsyncClient):
        resp = await client.get("/health/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "uptime_seconds" in body["data"]
        assert "version" in body["data"]


# --- Response Envelope ---


@pytest.mark.f3
class TestResponseEnvelope:
    """All API responses wrapped in standard envelope per §25.3."""

    async def test_envelope_has_required_fields(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        body = resp.json()
        required_keys = {"ok", "data", "error", "trace_id"}
        assert required_keys.issubset(body.keys())

    async def test_trace_id_is_valid_uuid(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        body = resp.json()
        # Should be a valid UUID string
        parsed = uuid.UUID(body["trace_id"])
        assert str(parsed) == body["trace_id"]


# --- Request ID Middleware ---


@pytest.mark.f3
class TestRequestIDMiddleware:
    """Every response includes X-Trace-ID header."""

    async def test_response_has_trace_id_header(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        assert "x-trace-id" in resp.headers
        # Header should be a valid UUID
        uuid.UUID(resp.headers["x-trace-id"])

    async def test_trace_id_header_matches_body(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        body = resp.json()
        assert resp.headers["x-trace-id"] == body["trace_id"]


# --- Error Handling ---


@pytest.mark.f3
class TestErrorHandling:
    """Error responses use envelope format."""

    async def test_404_returns_envelope(self, client: httpx.AsyncClient):
        resp = await client.get("/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert body["ok"] is False
        assert body["error"] is not None
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "trace_id" in body

    async def test_validation_error_returns_422_envelope(
        self, client: httpx.AsyncClient
    ):
        """POST to a typed endpoint with bad data returns 422 envelope."""
        resp = await client.get("/api/v1/health/echo?value=ok")
        assert resp.status_code == 200
        # Now send wrong type — the endpoint expects a query param
        # We test by omitting the required param
        resp = await client.get("/api/v1/health/echo")
        assert resp.status_code == 422
        body = resp.json()
        assert body["ok"] is False
        assert body["error"] is not None
        assert body["error"]["code"] == "VALIDATION_ERROR"


# --- API Versioning ---


@pytest.mark.f3
class TestAPIVersioning:
    """API routes are prefixed with /api/v1/."""

    async def test_v1_health_prefix(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

    async def test_openapi_spec_accessible(self, client: httpx.AsyncClient):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert "openapi" in spec
        assert spec["openapi"].startswith("3.1")
        assert "/health" in str(spec["paths"])
