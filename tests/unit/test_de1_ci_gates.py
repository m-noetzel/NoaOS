"""DE1 CI gate validator tests.

Validates the GitHub Actions workflow files (cd.yml, web-ci.yml, ios-ci.yml)
and that ci.yml has the Postgres service block. All tests are pure structural
checks against YAML files — no subprocess/docker calls.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent.parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

CD_PATH = WORKFLOWS / "cd.yml"
WEB_CI_PATH = WORKFLOWS / "web-ci.yml"
IOS_CI_PATH = WORKFLOWS / "ios-ci.yml"
CI_PATH = WORKFLOWS / "ci.yml"
PRE_PUSH_PATH = REPO / "tools" / "pre-push-hook.sh"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_workflow(path: Path) -> dict[str, Any]:
    """Load and normalise a workflow YAML file.

    PyYAML parses the bare YAML key 'on' as the Python boolean True.
    We normalise it back to the string 'on' for consistent test access.
    """
    assert path.exists(), f"Workflow file not found: {path}"
    with path.open() as f:
        data: dict[Any, Any] = yaml.safe_load(f)
    assert isinstance(data, dict), f"{path.name} must parse to a YAML mapping"
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cd_workflow() -> dict[str, Any]:
    return _load_workflow(CD_PATH)


@pytest.fixture(scope="module")
def web_ci_workflow() -> dict[str, Any]:
    return _load_workflow(WEB_CI_PATH)


@pytest.fixture(scope="module")
def ios_ci_workflow() -> dict[str, Any]:
    return _load_workflow(IOS_CI_PATH)


@pytest.fixture(scope="module")
def ci_workflow() -> dict[str, Any]:
    return _load_workflow(CI_PATH)


@pytest.fixture(scope="module")
def pre_push_content() -> str:
    assert PRE_PUSH_PATH.exists(), f"pre-push-hook.sh not found: {PRE_PUSH_PATH}"
    return PRE_PUSH_PATH.read_text()


# ── CD workflow ────────────────────────────────────────────────────────────────

def test_cd_workflow_exists() -> None:
    assert CD_PATH.exists(), "cd.yml must exist under .github/workflows/"


def test_cd_workflow_is_valid_yaml(cd_workflow: dict[str, Any]) -> None:
    assert cd_workflow is not None


def test_cd_has_build_push_action(cd_workflow: dict[str, Any]) -> None:
    jobs = cd_workflow.get("jobs", {})
    all_steps = []
    for job in jobs.values():
        all_steps.extend(job.get("steps", []))
    uses_values = [str(s.get("uses", "")) for s in all_steps]
    assert any("build-push-action" in u for u in uses_values), (
        "cd.yml must use docker/build-push-action"
    )


def test_cd_has_sha_tag(cd_workflow: dict[str, Any]) -> None:
    raw = CD_PATH.read_text()
    assert "github.sha" in raw, (
        "cd.yml must tag the image with ${{ github.sha }} for traceability"
    )


def test_cd_triggers_on_main_push_only(cd_workflow: dict[str, Any]) -> None:
    on = cd_workflow.get("on", {})
    assert "push" in on, "cd.yml must trigger on push"
    push_cfg = on["push"]
    assert "branches" in push_cfg, "cd.yml push trigger must specify branches"
    assert "main" in push_cfg["branches"], "cd.yml must deploy on push to main"
    # CD should NOT trigger on pull_request — only on merge to main
    assert "pull_request" not in on, (
        "cd.yml must only trigger on push to main, not on pull_request"
    )


def test_cd_has_packages_write_permission(cd_workflow: dict[str, Any]) -> None:
    perms = cd_workflow.get("permissions", {})
    assert perms.get("packages") == "write", (
        "cd.yml must have packages: write permission to push to GHCR"
    )


def test_cd_has_ghcr_login(cd_workflow: dict[str, Any]) -> None:
    raw = CD_PATH.read_text()
    assert "ghcr.io" in raw, "cd.yml must reference ghcr.io registry"
    assert "docker/login-action" in raw, "cd.yml must use docker/login-action"


def test_cd_job_has_timeout(cd_workflow: dict[str, Any]) -> None:
    jobs = cd_workflow.get("jobs", {})
    for job_name, job in jobs.items():
        assert "timeout-minutes" in job, (
            f"cd.yml job '{job_name}' must have timeout-minutes"
        )
        assert job["timeout-minutes"] <= 30, (
            f"cd.yml job '{job_name}' timeout must be <= 30 minutes"
        )


# ── Web CI workflow ────────────────────────────────────────────────────────────

def test_web_ci_workflow_exists() -> None:
    assert WEB_CI_PATH.exists(), "web-ci.yml must exist under .github/workflows/"


def test_web_ci_workflow_is_valid_yaml(web_ci_workflow: dict[str, Any]) -> None:
    assert web_ci_workflow is not None


def test_web_ci_has_e2e_step(web_ci_workflow: dict[str, Any]) -> None:
    jobs = web_ci_workflow.get("jobs", {})
    all_steps = []
    for job in jobs.values():
        all_steps.extend(job.get("steps", []))
    run_commands = " ".join(s.get("run", "") for s in all_steps)
    assert "test:e2e" in run_commands or "playwright" in run_commands.lower(), (
        "web-ci.yml must include an E2E test step"
    )


def test_web_ci_has_build_step(web_ci_workflow: dict[str, Any]) -> None:
    jobs = web_ci_workflow.get("jobs", {})
    all_steps = []
    for job in jobs.values():
        all_steps.extend(job.get("steps", []))
    run_commands = " ".join(s.get("run", "") for s in all_steps)
    assert "npm run build" in run_commands, (
        "web-ci.yml must include a build step to catch compilation errors"
    )


def test_web_ci_triggers_on_pr_and_push(web_ci_workflow: dict[str, Any]) -> None:
    on = web_ci_workflow.get("on", {})
    assert "push" in on, "web-ci.yml must trigger on push"
    assert "pull_request" in on, "web-ci.yml must trigger on pull_request"


def test_web_ci_has_npm_cache(web_ci_workflow: dict[str, Any]) -> None:
    jobs = web_ci_workflow.get("jobs", {})
    all_steps = []
    for job in jobs.values():
        all_steps.extend(job.get("steps", []))
    cache_steps = [s for s in all_steps if "cache" in str(s.get("uses", ""))]
    assert cache_steps, "web-ci.yml must cache npm dependencies"


def test_web_ci_job_has_timeout(web_ci_workflow: dict[str, Any]) -> None:
    jobs = web_ci_workflow.get("jobs", {})
    for job_name, job in jobs.items():
        assert "timeout-minutes" in job, (
            f"web-ci.yml job '{job_name}' must have timeout-minutes"
        )


# ── iOS CI workflow ────────────────────────────────────────────────────────────

def test_ios_ci_workflow_exists() -> None:
    assert IOS_CI_PATH.exists(), "ios-ci.yml must exist under .github/workflows/"


def test_ios_ci_workflow_is_valid_yaml(ios_ci_workflow: dict[str, Any]) -> None:
    assert ios_ci_workflow is not None


def test_ios_ci_has_swift_test(ios_ci_workflow: dict[str, Any]) -> None:
    jobs = ios_ci_workflow.get("jobs", {})
    all_steps = []
    for job in jobs.values():
        all_steps.extend(job.get("steps", []))
    run_commands = " ".join(s.get("run", "") for s in all_steps)
    assert "swift test" in run_commands, (
        "ios-ci.yml must run 'swift test'"
    )


def test_ios_ci_runs_on_macos(ios_ci_workflow: dict[str, Any]) -> None:
    jobs = ios_ci_workflow.get("jobs", {})
    for job_name, job in jobs.items():
        runner = job.get("runs-on", "")
        assert "macos" in str(runner), (
            f"ios-ci.yml job '{job_name}' must run on macOS (got '{runner}')"
        )


def test_ios_ci_triggers_on_pr_and_push(ios_ci_workflow: dict[str, Any]) -> None:
    on = ios_ci_workflow.get("on", {})
    assert "push" in on, "ios-ci.yml must trigger on push"
    assert "pull_request" in on, "ios-ci.yml must trigger on pull_request"


def test_ios_ci_job_has_timeout(ios_ci_workflow: dict[str, Any]) -> None:
    jobs = ios_ci_workflow.get("jobs", {})
    for job_name, job in jobs.items():
        assert "timeout-minutes" in job, (
            f"ios-ci.yml job '{job_name}' must have timeout-minutes"
        )


# ── All workflows have permissions ────────────────────────────────────────────

def test_all_workflows_have_permissions() -> None:
    for name, path in [("ci.yml", CI_PATH), ("cd.yml", CD_PATH),
                       ("web-ci.yml", WEB_CI_PATH), ("ios-ci.yml", IOS_CI_PATH)]:
        wf = _load_workflow(path)
        assert "permissions" in wf, (
            f"{name} must have a top-level 'permissions' block (least-privilege)"
        )


def test_all_workflows_have_timeout() -> None:
    for name, path in [("ci.yml", CI_PATH), ("cd.yml", CD_PATH),
                       ("web-ci.yml", WEB_CI_PATH), ("ios-ci.yml", IOS_CI_PATH)]:
        wf = _load_workflow(path)
        jobs = wf.get("jobs", {})
        for job_name, job in jobs.items():
            assert "timeout-minutes" in job, (
                f"{name} job '{job_name}' must have timeout-minutes"
            )


# ── ci.yml Postgres service ────────────────────────────────────────────────────

def test_ci_backend_job_has_postgres_service(ci_workflow: dict[str, Any]) -> None:
    backend_job = ci_workflow["jobs"]["test-backend"]
    services = backend_job.get("services", {})
    assert "postgres" in services, (
        "test-backend job in ci.yml must define a 'postgres' service"
    )


def test_ci_postgres_service_uses_postgres16(ci_workflow: dict[str, Any]) -> None:
    backend_job = ci_workflow["jobs"]["test-backend"]
    pg = backend_job.get("services", {}).get("postgres", {})
    assert "16" in str(pg.get("image", "")), (
        "postgres service must use postgres:16 image"
    )


def test_ci_postgres_service_has_health_check(ci_workflow: dict[str, Any]) -> None:
    backend_job = ci_workflow["jobs"]["test-backend"]
    pg = backend_job.get("services", {}).get("postgres", {})
    options = str(pg.get("options", ""))
    assert "pg_isready" in options or "health-cmd" in options, (
        "postgres service must have a health check (--health-cmd pg_isready)"
    )


def test_ci_postgres_service_has_port_mapping(ci_workflow: dict[str, Any]) -> None:
    backend_job = ci_workflow["jobs"]["test-backend"]
    pg = backend_job.get("services", {}).get("postgres", {})
    ports = pg.get("ports", [])
    assert any("5432" in str(p) for p in ports), (
        "postgres service must expose port 5432"
    )


# ── Dependency cache present in ci.yml and web-ci.yml ─────────────────────────

def test_dependency_cache_present(
    ci_workflow: dict[str, Any], web_ci_workflow: dict[str, Any]
) -> None:
    # ci.yml backend job must have pip cache
    backend_steps = ci_workflow["jobs"]["test-backend"]["steps"]
    backend_cache = [s for s in backend_steps if "cache" in str(s.get("uses", ""))]
    assert backend_cache, "ci.yml test-backend must have a cache step for pip"

    # web-ci.yml must have npm cache
    wci_jobs = web_ci_workflow.get("jobs", {})
    all_web_steps: list[dict[str, Any]] = []
    for job in wci_jobs.values():
        all_web_steps.extend(job.get("steps", []))
    web_cache = [s for s in all_web_steps if "cache" in str(s.get("uses", ""))]
    assert web_cache, "web-ci.yml must have a cache step for npm"


# ── Parallel jobs in ci.yml (no needs: chain) ─────────────────────────────────

def test_parallel_jobs_in_ci(ci_workflow: dict[str, Any]) -> None:
    """ci.yml must have >= 3 jobs that run in parallel (no needs: dependency chain)."""
    jobs = ci_workflow.get("jobs", {})
    assert len(jobs) >= 3, "ci.yml must define at least 3 jobs"
    # None of the three main jobs should depend on another
    independent = [
        name for name, job in jobs.items()
        if "needs" not in job
    ]
    assert len(independent) >= 3, (
        f"ci.yml must have >= 3 independent (parallel) jobs; "
        f"found {len(independent)}: {independent}"
    )


# ── CI triggers on both PR and push ───────────────────────────────────────────

def test_ci_triggers_on_pr_and_push(ci_workflow: dict[str, Any]) -> None:
    on = ci_workflow.get("on", {})
    assert "push" in on, "ci.yml must trigger on push"
    assert "pull_request" in on, "ci.yml must trigger on pull_request"


# ── Pre-push hook warning message ─────────────────────────────────────────────

def test_pre_push_warning_is_loud(pre_push_content: str) -> None:
    """Container-not-running warning must be prominent, not just an info line."""
    assert "WARNING" in pre_push_content, (
        "pre-push-hook.sh must print 'WARNING' when container is not running"
    )
    assert "SKIPPED" in pre_push_content, (
        "pre-push-hook.sh must print 'SKIPPED' so the user knows checks were bypassed"
    )
