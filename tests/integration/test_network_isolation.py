"""Tests for Docker Network Isolation & Verification -- Phase DW3.

Spec refs: SPEC.md Section 20.1, Section 20.3, Section 20.4, Section 7.3
Phase plan: MASTER_PLAN.md Phase DW3

These are declarative configuration-validation tests that parse
docker-compose.yml and inspect verify_isolation.sh.  They do NOT require
running Docker containers.

Tests cover:
  - Docker Compose network definitions (internal flag, existence)
  - Service-to-network assignments (private-worker, external-worker, noa-api, postgres)
  - Noa API bind address (127.0.0.1 only, never 0.0.0.0)
  - Egress allowlist for the external container per Section 20.3
  - Private container has no egress (relies on internal: true)
  - Verification script existence, permissions, and content patterns per Section 20.4
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.dw3

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
VERIFY_SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_isolation.sh"

# Expected egress allowlist per SPEC.md Section 20.3
EXPECTED_EGRESS_DOMAINS: set[str] = {
    "api.anthropic.com",
    "api.openai.com",
    # Google: explicit subdomains (more restrictive than *.googleapis.com wildcard)
    "generativelanguage.googleapis.com",
    "gmail.googleapis.com",
    "www.googleapis.com",
    "accounts.google.com",
    "oauth2.googleapis.com",
    "api.notion.com",
    "api.tavily.com",
    "registry.npmjs.org",
    "pypi.org",
    "files.pythonhosted.org",
}


@pytest.fixture(scope="module")
def compose_config() -> dict[str, Any]:
    """Load and return the parsed docker-compose.yml."""
    with open(COMPOSE_PATH) as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return data


@pytest.fixture(scope="module")
def compose_services(compose_config: dict[str, Any]) -> dict[str, Any]:
    """Return the 'services' block from docker-compose.yml."""
    services: dict[str, Any] = compose_config["services"]
    return services


@pytest.fixture(scope="module")
def compose_networks(compose_config: dict[str, Any]) -> dict[str, Any]:
    """Return the 'networks' block from docker-compose.yml."""
    networks: dict[str, Any] = compose_config["networks"]
    return networks


# ---------------------------------------------------------------------------
# 1. Docker Compose Config Validation
# ---------------------------------------------------------------------------


class TestDockerComposeNetworks:
    """Validate Docker Compose network definitions per SPEC.md Section 20.1."""

    def test_noa_internal_network_exists_and_is_internal(
        self, compose_networks: dict[str, Any],
    ) -> None:
        """noa-internal network must exist with internal: true (Section 20.1).

        The internal flag blocks all internet egress at the Docker network
        level, which is the primary isolation mechanism for the private domain.
        """
        assert "noa-internal" in compose_networks, (
            "noa-internal network not defined in docker-compose.yml"
        )
        net = compose_networks["noa-internal"]
        assert net.get("internal") is True, (
            "noa-internal network must have 'internal: true' to block egress"
        )

    def test_noa_external_network_exists(
        self, compose_networks: dict[str, Any],
    ) -> None:
        """noa-external network must exist (Section 20.1).

        This network allows internet access for LLM API calls from the
        external worker.
        """
        assert "noa-external" in compose_networks, (
            "noa-external network not defined in docker-compose.yml"
        )


class TestServiceNetworkAssignments:
    """Validate that each service is on exactly the correct network(s).

    Per SPEC.md Section 20.1 and Section 7.3:
      - private-worker: ONLY noa-internal
      - external-worker: ONLY noa-external
      - noa-api: BOTH noa-internal AND noa-external
      - postgres: ONLY noa-internal
    """

    @staticmethod
    def _get_service_networks(services: dict[str, Any], name: str) -> set[str]:
        """Extract the set of network names a service is attached to."""
        svc = services[name]
        nets = svc.get("networks", [])
        if isinstance(nets, list):
            return set(nets)
        if isinstance(nets, dict):
            return set(nets.keys())
        msg = f"Unexpected networks type for {name}: {type(nets)}"
        raise TypeError(msg)

    def test_private_worker_only_on_internal(
        self, compose_services: dict[str, Any],
    ) -> None:
        nets = self._get_service_networks(compose_services, "private-worker")
        assert nets == {"noa-internal"}, (
            f"private-worker must be ONLY on noa-internal, got {nets}"
        )

    def test_external_worker_only_on_external(
        self, compose_services: dict[str, Any],
    ) -> None:
        nets = self._get_service_networks(compose_services, "external-worker")
        assert nets == {"noa-external"}, (
            f"external-worker must be ONLY on noa-external, got {nets}"
        )

    def test_noa_api_on_both_networks(
        self, compose_services: dict[str, Any],
    ) -> None:
        nets = self._get_service_networks(compose_services, "noa-api")
        assert nets == {"noa-internal", "noa-external"}, (
            f"noa-api must be on BOTH noa-internal and noa-external, got {nets}"
        )

    def test_postgres_only_on_internal(
        self, compose_services: dict[str, Any],
    ) -> None:
        nets = self._get_service_networks(compose_services, "postgres")
        assert nets == {"noa-internal"}, (
            f"postgres must be ONLY on noa-internal, got {nets}"
        )


class TestNoaApiBindAddress:
    """Verify noa-api binds to 127.0.0.1, never 0.0.0.0 (Section 20.1)."""

    def test_api_port_binding_is_localhost_only(
        self, compose_services: dict[str, Any],
    ) -> None:
        """Port mappings must bind to 127.0.0.1, not 0.0.0.0 or bare port."""
        api_svc = compose_services["noa-api"]
        ports = api_svc.get("ports", [])
        assert ports, "noa-api must define port mappings"

        for port_spec in ports:
            port_str = str(port_spec)
            assert port_str.startswith("127.0.0.1:"), (
                f"noa-api port binding must start with '127.0.0.1:', "
                f"got '{port_str}'. Binding to 0.0.0.0 exposes the API "
                f"beyond localhost (Section 20.1)."
            )


# ---------------------------------------------------------------------------
# 2. Egress Allowlist Validation
# ---------------------------------------------------------------------------


class TestEgressAllowlist:
    """Validate egress configuration per SPEC.md Section 20.3.

    Section 20.3 specifies:
      - External container has an egress allowlist of specific domains
      - All other egress is blocked via Docker network policy
      - DNS queries are logged for audit
    """

    def test_external_worker_has_egress_allowlist(
        self, compose_services: dict[str, Any],
    ) -> None:
        """external-worker must define an egress allowlist label or config.

        The allowlist is stored as a Docker label 'noa.egress.allowlist'
        containing comma-separated domains.
        """
        svc = compose_services["external-worker"]
        labels = svc.get("labels", {})
        # Support both dict and list-of-str label formats
        if isinstance(labels, list):
            label_dict: dict[str, str] = {}
            for item in labels:
                k, _, v = str(item).partition("=")
                label_dict[k] = v
            labels = label_dict

        assert "noa.egress.allowlist" in labels, (
            "external-worker must have a 'noa.egress.allowlist' label "
            "listing allowed egress domains (Section 20.3)"
        )
        allowlist_raw = labels["noa.egress.allowlist"]
        actual_domains = {d.strip() for d in allowlist_raw.split(",")}
        assert actual_domains == EXPECTED_EGRESS_DOMAINS, (
            f"Egress allowlist mismatch.\n"
            f"  Expected: {sorted(EXPECTED_EGRESS_DOMAINS)}\n"
            f"  Actual:   {sorted(actual_domains)}"
        )

    def test_private_worker_has_no_egress_config(
        self, compose_services: dict[str, Any],
    ) -> None:
        """private-worker must NOT define any egress allowlist.

        The private container relies on the noa-internal network's
        'internal: true' flag to block all egress. No allowlist is
        needed or desired.
        """
        svc = compose_services["private-worker"]
        labels = svc.get("labels", {})
        if isinstance(labels, list):
            label_keys = {str(item).partition("=")[0] for item in labels}
        elif isinstance(labels, dict):
            label_keys = set(labels.keys())
        else:
            label_keys = set()

        assert "noa.egress.allowlist" not in label_keys, (
            "private-worker must NOT have an egress allowlist; "
            "it should have no internet access at all (internal: true)"
        )

    def test_external_worker_dns_logging_enabled(
        self, compose_services: dict[str, Any],
    ) -> None:
        """external-worker should have DNS logging enabled for audit.

        Per Section 20.3, DNS queries must be logged for audit. This is
        indicated by the 'noa.dns.logging' label set to 'true'.
        """
        svc = compose_services["external-worker"]
        labels = svc.get("labels", {})
        if isinstance(labels, list):
            label_dict_dns: dict[str, str] = {}
            for item in labels:
                k, _, v = str(item).partition("=")
                label_dict_dns[k] = v
            labels = label_dict_dns

        assert labels.get("noa.dns.logging") == "true", (
            "external-worker must have 'noa.dns.logging: true' label "
            "for DNS audit logging (Section 20.3)"
        )


# ---------------------------------------------------------------------------
# 3. Verification Script Validation
# ---------------------------------------------------------------------------


class TestVerificationScript:
    """Validate verify_isolation.sh per SPEC.md Section 20.4.

    The script implements the continuous verification tests defined in the
    spec: private container egress, DNS resolution, and IPv6 egress tests.
    """

    def test_verify_script_exists(self) -> None:
        """scripts/verify_isolation.sh must exist."""
        assert VERIFY_SCRIPT_PATH.exists(), (
            f"Verification script not found at {VERIFY_SCRIPT_PATH}. "
            f"Section 20.4 requires a continuous verification script."
        )

    def test_verify_script_is_executable(self) -> None:
        """scripts/verify_isolation.sh must be executable."""
        assert VERIFY_SCRIPT_PATH.exists(), (
            f"Cannot check permissions: {VERIFY_SCRIPT_PATH} does not exist"
        )
        mode = os.stat(VERIFY_SCRIPT_PATH).st_mode
        assert mode & stat.S_IXUSR, (
            "verify_isolation.sh must be executable (owner execute bit not set)"
        )

    def test_verify_script_tests_private_egress(self) -> None:
        """Script must test private container egress (curl must fail).

        Per Section 20.4: curl -s --max-time 5 https://canary.example.com
        from inside the private container. Alert on SUCCESS (should always fail).
        """
        assert VERIFY_SCRIPT_PATH.exists(), (
            f"Cannot check content: {VERIFY_SCRIPT_PATH} does not exist"
        )
        content = VERIFY_SCRIPT_PATH.read_text()
        assert "private" in content.lower(), (
            "Script must reference the private container/worker for egress test"
        )
        assert "curl" in content, (
            "Script must use curl to test egress from private container "
            "(Section 20.4)"
        )

    def test_verify_script_tests_dns_resolution(self) -> None:
        """Script must test DNS resolution from private container.

        Per Section 20.4: nslookup google.com from inside the private
        container. Alert on SUCCESS (should always fail).
        """
        assert VERIFY_SCRIPT_PATH.exists(), (
            f"Cannot check content: {VERIFY_SCRIPT_PATH} does not exist"
        )
        content = VERIFY_SCRIPT_PATH.read_text()
        # Accept nslookup, dig, or host as DNS resolution tools
        has_dns_test = (
            "nslookup" in content or "dig " in content or "host " in content
        )
        assert has_dns_test, (
            "Script must test DNS resolution from private container "
            "(nslookup/dig/host) per Section 20.4"
        )

    def test_verify_script_tests_ipv6_egress(self) -> None:
        """Script must test IPv6 egress from private container.

        Per Section 20.4: curl -6 https://canary.example.com from inside
        the private container. Alert on SUCCESS (should always fail).
        """
        assert VERIFY_SCRIPT_PATH.exists(), (
            f"Cannot check content: {VERIFY_SCRIPT_PATH} does not exist"
        )
        content = VERIFY_SCRIPT_PATH.read_text()
        # Look for IPv6 test indicators: curl -6, or ipv6 mention
        has_ipv6_test = "curl -6" in content or "ipv6" in content.lower()
        assert has_ipv6_test, (
            "Script must test IPv6 egress from private container "
            "(curl -6) per Section 20.4"
        )

    def test_verify_script_has_shebang(self) -> None:
        """Script must have a proper shebang line."""
        assert VERIFY_SCRIPT_PATH.exists(), (
            f"Cannot check content: {VERIFY_SCRIPT_PATH} does not exist"
        )
        content = VERIFY_SCRIPT_PATH.read_text()
        first_line = content.strip().split("\n")[0]
        assert first_line.startswith("#!/"), (
            f"verify_isolation.sh must start with a shebang (#!/bin/bash or "
            f"#!/usr/bin/env bash), got: {first_line!r}"
        )
