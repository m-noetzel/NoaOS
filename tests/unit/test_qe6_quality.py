"""QE6 — Test Quality Infrastructure: coverage, mutation testing, flaky detection.

These tests verify that the quality tooling configuration is correct and functional.
They check configuration files (pyproject.toml, ci.yml, .gitignore) and verify
that coverage can actually run and produce a report — not just that config keys exist.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
GITIGNORE = ROOT / ".gitignore"
TRACEABILITY = ROOT / "Plan" / "TRACEABILITY.md"


# ---------------------------------------------------------------------------
# 1. pyproject.toml — dev dependencies present
# ---------------------------------------------------------------------------


def _read_pyproject() -> str:
    return PYPROJECT.read_text()


def test_pytest_cov_in_dev_deps() -> None:
    """pytest-cov must be listed as a dev dependency."""
    content = _read_pyproject()
    assert "pytest-cov" in content, "pytest-cov not found in pyproject.toml"


def test_pytest_repeat_in_dev_deps() -> None:
    """pytest-repeat must be listed as a dev dependency for flaky detection."""
    content = _read_pyproject()
    assert "pytest-repeat" in content, "pytest-repeat not found in pyproject.toml"


def test_mutmut_in_dev_deps() -> None:
    """mutmut must be listed as a dev dependency for mutation testing."""
    content = _read_pyproject()
    assert "mutmut" in content, "mutmut not found in pyproject.toml"


# ---------------------------------------------------------------------------
# 2. pyproject.toml — coverage configuration
# ---------------------------------------------------------------------------


def test_coverage_fail_under_configured() -> None:
    """Coverage threshold (fail_under) must be set in [tool.coverage.report]."""
    content = _read_pyproject()
    assert "[tool.coverage.report]" in content
    assert "fail_under" in content, "fail_under threshold not configured"


def test_coverage_threshold_is_70_or_higher() -> None:
    """Coverage threshold must be >= 70 (realistic baseline)."""
    content = _read_pyproject()
    # Find the line: fail_under = <N>
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("fail_under"):
            _, _, value = stripped.partition("=")
            threshold = int(value.strip())
            assert threshold >= 70, f"Coverage threshold {threshold} is below 70%"
            return
    pytest.fail("fail_under not found in pyproject.toml coverage config")


def test_coverage_source_points_to_noa() -> None:
    """Coverage source must point to src/noa."""
    content = _read_pyproject()
    assert '[tool.coverage.run]' in content
    assert 'source = ["src/noa"]' in content or "src/noa" in content


def test_coverage_html_directory_configured() -> None:
    """HTML coverage report directory must be configured (htmlcov)."""
    content = _read_pyproject()
    assert "[tool.coverage.html]" in content
    assert "htmlcov" in content


def test_mutmut_targets_critical_paths() -> None:
    """mutmut config must target auth, router, and gateway — the critical paths."""
    content = _read_pyproject()
    assert "[tool.mutmut]" in content
    assert "src/noa/auth/" in content
    assert "router.py" in content
    assert "gateway.py" in content


# ---------------------------------------------------------------------------
# 3. .gitignore — build artifacts excluded
# ---------------------------------------------------------------------------


def test_gitignore_excludes_htmlcov() -> None:
    """htmlcov/ must be in .gitignore — coverage HTML reports are not committed."""
    content = GITIGNORE.read_text()
    assert "htmlcov/" in content, "htmlcov/ missing from .gitignore"


def test_gitignore_excludes_mutmut_cache() -> None:
    """.mutmut-cache/ must be in .gitignore."""
    content = GITIGNORE.read_text()
    assert ".mutmut-cache/" in content, ".mutmut-cache/ missing from .gitignore"


# ---------------------------------------------------------------------------
# 4. CI workflow — coverage and flaky detection jobs
# ---------------------------------------------------------------------------


def test_ci_has_coverage_step() -> None:
    """CI workflow must run pytest with --cov and --cov-fail-under."""
    content = CI_YML.read_text()
    assert "--cov=src/noa" in content, "--cov=src/noa not found in CI workflow"
    assert "--cov-fail-under=70" in content, "--cov-fail-under=70 not found in CI"


def test_ci_uploads_coverage_artifact() -> None:
    """CI must upload the coverage HTML report as an artifact."""
    content = CI_YML.read_text()
    assert "coverage-report" in content, "coverage-report artifact upload missing from CI"
    assert "htmlcov" in content


def test_ci_has_nightly_flaky_job() -> None:
    """CI must have a flaky-test-detection job triggered by schedule."""
    content = CI_YML.read_text()
    assert "flaky-test-detection" in content, "flaky-test-detection job missing from CI"
    assert "--count=3" in content, "--count=3 (pytest-repeat) not used in flaky detection"


def test_ci_has_schedule_trigger() -> None:
    """CI workflow must have a cron schedule trigger for the nightly flaky job."""
    content = CI_YML.read_text()
    assert "schedule:" in content, "schedule trigger missing from CI workflow"
    assert "cron:" in content


# ---------------------------------------------------------------------------
# 5. Mutation testing baseline documented
# ---------------------------------------------------------------------------


def test_traceability_has_mutation_baseline_section() -> None:
    """TRACEABILITY.md must have a mutation testing baseline section (QE6)."""
    content = TRACEABILITY.read_text()
    assert "Mutation Testing Baseline" in content, (
        "Mutation Testing Baseline section missing from Plan/TRACEABILITY.md"
    )
    assert "mutmut" in content


# ---------------------------------------------------------------------------
# 6. Meta-test: coverage can actually run (functional smoke test)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_coverage_runs_on_minimal_example() -> None:
    """Coverage can collect data and produce a term report on a real module.

    This is a meta-test that proves the coverage tooling is functional, not just
    configured. It runs pytest --cov on a test that imports src/noa code (config)
    and verifies the output contains a coverage table. We disable fail-under here
    because we're only running a subset of tests — the threshold applies to the
    full suite.
    """
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/test_config.py",
            "--cov=src/noa",
            "--cov-report=term-missing",
            "--no-cov-on-fail",
            "--tb=short",
            "-q",
            # Override fail_under for this subset run — subset coverage will be low
            "--cov-fail-under=0",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    combined = result.stdout + result.stderr
    # Coverage table appears with "TOTAL" line
    assert "TOTAL" in combined, (
        f"Coverage table not in output. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert result.returncode == 0, (
        f"Coverage run failed (exit {result.returncode}):\n{combined}"
    )
