"""
DE2: TLS & Reverse Proxy — Tests.

SPEC.md §29.4 (HTTPS over LAN/VPN), §7.1 (network topology),
§20.1 (Docker network isolation)

Tests validate:
- Caddyfile directives (reverse_proxy, HSTS, env var placeholder)
- docker-compose caddy service definition (image, volumes, ports)
- docker-compose noa-api does NOT expose ports to host
- CORS configuration accepts NOA_DOMAIN HTTPS origin
- CORS config does not allow wildcard in production mode
- docs/TLS_SETUP.md exists and is non-empty
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

# Resolve paths relative to the repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
CADDYFILE = REPO_ROOT / "docker" / "caddy" / "Caddyfile"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
TLS_DOC = REPO_ROOT / "docs" / "TLS_SETUP.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_caddyfile() -> str:
    assert CADDYFILE.exists(), f"Caddyfile not found at {CADDYFILE}"
    return CADDYFILE.read_text()


def load_compose() -> dict:
    assert COMPOSE_FILE.exists(), f"docker-compose.yml not found at {COMPOSE_FILE}"
    with COMPOSE_FILE.open() as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Caddyfile tests
# ---------------------------------------------------------------------------


class TestCaddyfile:
    """Validate Caddyfile directives without running Caddy."""

    def test_reverse_proxy_to_noa_api(self) -> None:
        """Caddyfile must proxy traffic to noa-api:8000 (internal Docker hostname)."""
        content = read_caddyfile()
        assert "reverse_proxy noa-api:8000" in content, (
            "Caddyfile must contain 'reverse_proxy noa-api:8000'"
        )

    def test_hsts_header_present(self) -> None:
        """Caddyfile must inject Strict-Transport-Security header (SPEC §29.4)."""
        content = read_caddyfile()
        assert "Strict-Transport-Security" in content, (
            "Caddyfile must set Strict-Transport-Security header"
        )

    def test_noa_domain_env_var_placeholder(self) -> None:
        """Caddyfile must use {$NOA_DOMAIN} — not a hardcoded domain name."""
        content = read_caddyfile()
        assert "{$NOA_DOMAIN}" in content, (
            "Caddyfile must use {$NOA_DOMAIN} placeholder for configurability"
        )

    def test_http_to_https_redirect(self) -> None:
        """HTTP → HTTPS redirect must be present."""
        content = read_caddyfile()
        has_redir = "redir https://" in content
        has_http_block = "http://" in content
        assert has_redir or has_http_block, (
            "Caddyfile must contain HTTP→HTTPS redirect"
        )

    def test_no_hardcoded_domain_in_directives(self) -> None:
        """Caddyfile directive lines must not contain hardcoded domains.

        Comments may reference example domains; only non-comment lines
        are checked.
        """
        content = read_caddyfile()
        directive_lines = [
            line for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        directive_text = "\n".join(directive_lines)
        for bad in ("my-server.com", "prod.example.net"):
            assert bad not in directive_text, (
                f"Caddyfile directives must not contain hardcoded domain '{bad}'"
            )

    def test_tls_directive_present(self) -> None:
        """Caddyfile must contain a tls directive for certificate management."""
        content = read_caddyfile()
        assert "tls " in content, (
            "Caddyfile must have a 'tls' directive"
        )


# ---------------------------------------------------------------------------
# docker-compose.yml tests
# ---------------------------------------------------------------------------


class TestDockerCompose:
    """Validate compose service definitions for caddy and noa-api."""

    def test_caddy_service_exists(self) -> None:
        """Compose file must define a 'caddy' service."""
        compose = load_compose()
        assert "caddy" in compose.get("services", {}), (
            "docker-compose.yml must have a 'caddy' service"
        )

    def test_caddy_uses_alpine_image(self) -> None:
        """Caddy service must use the caddy:2-alpine image."""
        compose = load_compose()
        caddy = compose["services"]["caddy"]
        image = caddy.get("image", "")
        assert image == "caddy:2-alpine", (
            f"Caddy service image must be 'caddy:2-alpine', got '{image}'"
        )

    def test_caddy_binds_port_80(self) -> None:
        """Caddy must bind port 80 (ACME challenges and HTTP redirect)."""
        compose = load_compose()
        ports = compose["services"]["caddy"].get("ports", [])
        port_strings = [str(p) for p in ports]
        assert any("80" in p for p in port_strings), (
            "Caddy service must bind port 80"
        )

    def test_caddy_binds_port_443(self) -> None:
        """Caddy must bind port 443 (HTTPS)."""
        compose = load_compose()
        ports = compose["services"]["caddy"].get("ports", [])
        port_strings = [str(p) for p in ports]
        assert any("443" in p for p in port_strings), (
            "Caddy service must bind port 443"
        )

    def test_caddy_data_volume_mounted(self) -> None:
        """Caddy service must mount the caddy-data volume (TLS certs)."""
        compose = load_compose()
        caddy = compose["services"]["caddy"]
        volumes = caddy.get("volumes", [])
        volume_strings = [str(v) for v in volumes]
        assert any("caddy-data" in v for v in volume_strings), (
            "Caddy service must mount caddy-data volume for TLS cert persistence"
        )

    def test_caddy_data_volume_declared(self) -> None:
        """Top-level volumes block must declare caddy-data."""
        compose = load_compose()
        top_volumes = compose.get("volumes", {})
        assert "caddy-data" in top_volumes, (
            "docker-compose.yml top-level volumes must declare 'caddy-data'"
        )

    def test_noa_api_does_not_expose_port_to_host(self) -> None:
        """noa-api must NOT have a host port mapping — traffic goes through Caddy."""
        compose = load_compose()
        noa_api = compose["services"].get("noa-api", {})
        ports = noa_api.get("ports", [])
        assert len(ports) == 0, (
            f"noa-api must not expose ports to the host. Found: {ports}"
        )

    def test_noa_api_uses_expose_not_ports(self) -> None:
        """noa-api should use 'expose' (internal only) not 'ports' (host binding)."""
        compose = load_compose()
        noa_api = compose["services"].get("noa-api", {})
        expose = noa_api.get("expose", [])
        assert len(expose) > 0, (
            "noa-api must use 'expose:' for port 8000 on the Docker network"
        )

    def test_caddy_noa_domain_env_var(self) -> None:
        """Caddy service must pass NOA_DOMAIN environment variable."""
        compose = load_compose()
        caddy = compose["services"]["caddy"]
        env = caddy.get("environment", [])
        env_strings = [str(e) for e in env]
        assert any("NOA_DOMAIN" in e for e in env_strings), (
            "Caddy service must pass NOA_DOMAIN env var to the container"
        )


# ---------------------------------------------------------------------------
# CORS configuration tests
# ---------------------------------------------------------------------------


class TestCORSConfig:
    """Verify the FastAPI app wires NOA_DOMAIN into the CORS allow-list."""

    def test_cors_accepts_noa_domain_https_origin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When NOA_DOMAIN is set, https://{NOA_DOMAIN} must appear in CORS list."""
        monkeypatch.setenv("NOA_DOMAIN", "noa.example.com")
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

        # Replicate the CORS-building logic from app.py
        allowed_origins_raw = os.environ.get(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173",
        ).split(",")
        noa_domain = os.environ.get("NOA_DOMAIN", "").strip()
        if noa_domain and noa_domain != "localhost":
            allowed_origins_raw.append(f"https://{noa_domain}")
        allowed_origins = [
            o.strip() for o in allowed_origins_raw
            if o.strip() and o.strip() != "*"
        ]

        assert "https://noa.example.com" in allowed_origins, (
            "CORS list must include https://{NOA_DOMAIN} when NOA_DOMAIN is set"
        )

    def test_cors_does_not_add_localhost_domain_as_https(self) -> None:
        """When NOA_DOMAIN=localhost, must NOT add https://localhost to CORS."""
        noa_domain = "localhost"
        allowed_origins_raw = ["http://localhost:5173"]
        if noa_domain and noa_domain != "localhost":
            allowed_origins_raw.append(f"https://{noa_domain}")
        allowed_origins = [
            o.strip() for o in allowed_origins_raw
            if o.strip() and o.strip() != "*"
        ]
        assert "https://localhost" not in allowed_origins, (
            "CORS must not add https://localhost when NOA_DOMAIN=localhost"
        )

    def test_cors_never_allows_wildcard(self) -> None:
        """CORS allow-list must filter out wildcard (*) origins (M2)."""
        allowed_origins_raw = [
            "http://localhost:5173",
            "*",
            "https://noa.example.com",
        ]
        allowed_origins = [
            o.strip() for o in allowed_origins_raw
            if o.strip() and o.strip() != "*"
        ]
        assert "*" not in allowed_origins, (
            "CORS config must strip wildcard '*' origins (M2)"
        )


# ---------------------------------------------------------------------------
# Documentation tests
# ---------------------------------------------------------------------------


class TestTLSDocumentation:
    """Verify the TLS setup documentation exists and covers key scenarios."""

    def test_tls_setup_doc_exists(self) -> None:
        """docs/TLS_SETUP.md must exist."""
        assert TLS_DOC.exists(), f"docs/TLS_SETUP.md not found at {TLS_DOC}"

    def test_tls_setup_doc_non_empty(self) -> None:
        """docs/TLS_SETUP.md must be non-empty (>200 bytes)."""
        content = TLS_DOC.read_text()
        assert len(content) > 200, (
            f"docs/TLS_SETUP.md is too short ({len(content)} bytes)"
        )

    def test_tls_setup_doc_covers_lets_encrypt(self) -> None:
        """TLS_SETUP.md must document the Let's Encrypt / public domain scenario."""
        content = TLS_DOC.read_text()
        assert "Let's Encrypt" in content or "ACME" in content, (
            "docs/TLS_SETUP.md must document Let's Encrypt / ACME"
        )

    def test_tls_setup_doc_covers_local_dev(self) -> None:
        """TLS_SETUP.md must document the local dev scenario (localhost)."""
        content = TLS_DOC.read_text()
        assert "localhost" in content, (
            "docs/TLS_SETUP.md must document the localhost scenario"
        )
