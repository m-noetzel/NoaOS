"""
DE1: CI/CD Pipeline — Tests

Validates that the GitHub Actions workflow and local pre-push hook are
correctly structured and contain all required elements.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PRE_PUSH_PATH = REPO_ROOT / "tools" / "pre-push-hook.sh"
INSTALL_HOOKS_PATH = REPO_ROOT / "tools" / "install-hooks.sh"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    """Parse ci.yml and return the workflow dict.

    PyYAML parses the bare word 'on' as the Python boolean True (YAML 1.1
    boolean synonyms).  We normalise the key so tests can use the string 'on'.
    """
    assert WORKFLOW_PATH.exists(), f"Workflow file not found: {WORKFLOW_PATH}"
    with WORKFLOW_PATH.open() as f:
        data: dict[Any, Any] = yaml.safe_load(f)
    assert isinstance(data, dict), "ci.yml must parse to a YAML dict"
    # Normalise PyYAML's True -> "on" quirk
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


@pytest.fixture(scope="module")
def pre_push_content() -> str:
    """Return contents of pre-push-hook.sh."""
    assert PRE_PUSH_PATH.exists(), f"pre-push-hook.sh not found: {PRE_PUSH_PATH}"
    return PRE_PUSH_PATH.read_text()


# ── Workflow file existence and parse ─────────────────────────────────────────

def test_workflow_file_exists() -> None:
    assert WORKFLOW_PATH.exists(), "ci.yml must exist under .github/workflows/"


def test_workflow_is_valid_yaml(workflow: dict[str, Any]) -> None:
    # If the fixture returns, YAML parsed successfully
    assert workflow is not None


def test_workflow_has_name(workflow: dict[str, Any]) -> None:
    assert "name" in workflow, "Workflow must have a 'name' key"
    assert workflow["name"] == "CI"


# ── Trigger events ────────────────────────────────────────────────────────────

def test_workflow_triggers_on_push(workflow: dict[str, Any]) -> None:
    on = workflow.get("on", {})
    assert "push" in on, "Workflow must trigger on 'push'"


def test_workflow_triggers_on_pull_request(workflow: dict[str, Any]) -> None:
    on = workflow.get("on", {})
    assert "pull_request" in on, "Workflow must trigger on 'pull_request'"


def test_workflow_push_targets_main(workflow: dict[str, Any]) -> None:
    push_cfg = workflow["on"]["push"]
    assert "branches" in push_cfg, "push trigger must specify branches"
    assert "main" in push_cfg["branches"], "push must target 'main' branch"


def test_workflow_pr_targets_main(workflow: dict[str, Any]) -> None:
    pr_cfg = workflow["on"]["pull_request"]
    assert "branches" in pr_cfg, "pull_request trigger must specify branches"
    assert "main" in pr_cfg["branches"], "pull_request must target 'main' branch"


# ── Required jobs ─────────────────────────────────────────────────────────────

def test_workflow_has_jobs(workflow: dict[str, Any]) -> None:
    assert "jobs" in workflow, "Workflow must define jobs"
    assert isinstance(workflow["jobs"], dict)


def test_workflow_has_backend_test_job(workflow: dict[str, Any]) -> None:
    assert "test-backend" in workflow["jobs"], "Workflow must have 'test-backend' job"


def test_workflow_has_frontend_test_job(workflow: dict[str, Any]) -> None:
    assert "test-frontend" in workflow["jobs"], "Workflow must have 'test-frontend' job"


def test_workflow_has_static_analysis_job(workflow: dict[str, Any]) -> None:
    assert "static-analysis" in workflow["jobs"], (
        "Workflow must have 'static-analysis' job"
    )


# ── Backend job contents ──────────────────────────────────────────────────────

def test_backend_job_uses_python_312(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["test-backend"]["steps"]
    setup_steps = [s for s in steps if "setup-python" in str(s.get("uses", ""))]
    assert setup_steps, "test-backend must have a setup-python step"
    python_version = setup_steps[0].get("with", {}).get("python-version", "")
    assert "3.12" in str(python_version), "test-backend must use Python 3.12"


def test_backend_job_runs_pytest(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["test-backend"]["steps"]
    run_commands = " ".join(s.get("run", "") for s in steps)
    assert "pytest" in run_commands, "test-backend must run pytest"
    assert "tests/unit/" in run_commands, "test-backend must run tests/unit/"


def test_backend_job_has_pip_cache(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["test-backend"]["steps"]
    cache_steps = [s for s in steps if "cache" in str(s.get("uses", ""))]
    assert cache_steps, "test-backend must cache pip dependencies"


# ── Frontend job contents ─────────────────────────────────────────────────────

def test_frontend_job_uses_node_20(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["test-frontend"]["steps"]
    setup_steps = [s for s in steps if "setup-node" in str(s.get("uses", ""))]
    assert setup_steps, "test-frontend must have a setup-node step"
    node_version = setup_steps[0].get("with", {}).get("node-version", "")
    assert "20" in str(node_version), "test-frontend must use Node 20"


def test_frontend_job_runs_npm_test(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["test-frontend"]["steps"]
    run_commands = " ".join(s.get("run", "") for s in steps)
    assert "npm" in run_commands, "test-frontend must run npm commands"
    assert "test" in run_commands, "test-frontend must run tests"


def test_frontend_job_has_npm_cache(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["test-frontend"]["steps"]
    cache_steps = [s for s in steps if "cache" in str(s.get("uses", ""))]
    assert cache_steps, "test-frontend must cache npm dependencies"


# ── Static analysis job contents ──────────────────────────────────────────────

def test_static_analysis_runs_ruff(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["static-analysis"]["steps"]
    run_commands = " ".join(s.get("run", "") for s in steps)
    assert "ruff" in run_commands, "static-analysis must run ruff"


def test_static_analysis_runs_mypy(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["static-analysis"]["steps"]
    run_commands = " ".join(s.get("run", "") for s in steps)
    assert "mypy" in run_commands, "static-analysis must run mypy"


# ── No secrets in workflow ────────────────────────────────────────────────────

def test_no_plaintext_secrets_in_workflow() -> None:
    content = WORKFLOW_PATH.read_text()
    # Ensure any secret references use GitHub Secrets syntax, not literals
    # Workflow may reference ${{ secrets.XXX }} but must not have bare tokens
    suspicious_patterns = ["sk-", "ghp_", "xoxb-", "Bearer eyJ"]
    for pattern in suspicious_patterns:
        assert pattern not in content, (
            f"Workflow file contains suspicious pattern '{pattern}' — "
            "use GitHub Secrets references instead"
        )


# ── Workflow permissions ──────────────────────────────────────────────────────

def test_workflow_has_permissions_block(workflow: dict[str, Any]) -> None:
    assert "permissions" in workflow, (
        "Workflow must have a top-level 'permissions' block (least-privilege principle)"
    )


def test_workflow_permissions_contents_read(workflow: dict[str, Any]) -> None:
    perms = workflow.get("permissions", {})
    assert perms.get("contents") == "read", (
        "Workflow permissions must set 'contents: read'"
    )


# ── Job timeouts ──────────────────────────────────────────────────────────────

def test_backend_job_has_timeout(workflow: dict[str, Any]) -> None:
    job = workflow["jobs"]["test-backend"]
    assert "timeout-minutes" in job, "test-backend job must have timeout-minutes"
    assert job["timeout-minutes"] <= 30, "test-backend timeout must be <= 30 minutes"


def test_frontend_job_has_timeout(workflow: dict[str, Any]) -> None:
    job = workflow["jobs"]["test-frontend"]
    assert "timeout-minutes" in job, "test-frontend job must have timeout-minutes"
    assert job["timeout-minutes"] <= 30, "test-frontend timeout must be <= 30 minutes"


def test_static_analysis_job_has_timeout(workflow: dict[str, Any]) -> None:
    job = workflow["jobs"]["static-analysis"]
    assert "timeout-minutes" in job, "static-analysis job must have timeout-minutes"
    assert job["timeout-minutes"] <= 30, "static-analysis timeout must be <= 30 minutes"


# ── Backend job env vars ───────────────────────────────────────────────────────

def test_backend_job_has_env_vars(workflow: dict[str, Any]) -> None:
    job = workflow["jobs"]["test-backend"]
    assert "env" in job, (
        "test-backend job must have an 'env' block "
        "(Settings model requires DATABASE_URL, SECRET_KEY, NOA_ENV at import time)"
    )


def test_backend_job_env_has_database_url(workflow: dict[str, Any]) -> None:
    env = workflow["jobs"]["test-backend"].get("env", {})
    assert "DATABASE_URL" in env, "test-backend env must include DATABASE_URL"


def test_backend_job_env_has_secret_key(workflow: dict[str, Any]) -> None:
    env = workflow["jobs"]["test-backend"].get("env", {})
    assert "SECRET_KEY" in env, "test-backend env must include SECRET_KEY"


def test_backend_job_env_has_noa_env(workflow: dict[str, Any]) -> None:
    env = workflow["jobs"]["test-backend"].get("env", {})
    assert "NOA_ENV" in env, "test-backend env must include NOA_ENV"


# ── npm cache path ────────────────────────────────────────────────────────────

def test_frontend_npm_cache_uses_dot_npm(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["test-frontend"]["steps"]
    cache_steps = [s for s in steps if "cache" in str(s.get("uses", ""))]
    assert cache_steps, "test-frontend must have a cache step"
    cache_path = cache_steps[0].get("with", {}).get("path", "")
    assert "~/.npm" in str(cache_path), (
        "test-frontend npm cache must use '~/.npm' not 'web/node_modules' "
        "(~/.npm is the npm cache dir; node_modules is not portable across installs)"
    )


# ── Mypy without --ignore-missing-imports flag ────────────────────────────────

def test_static_analysis_mypy_reads_pyproject(workflow: dict[str, Any]) -> None:
    steps = workflow["jobs"]["static-analysis"]["steps"]
    run_commands = " ".join(s.get("run", "") for s in steps)
    assert "--ignore-missing-imports" not in run_commands, (
        "mypy must not use --ignore-missing-imports on the command line; "
        "per-module overrides belong in pyproject.toml [[tool.mypy.overrides]]"
    )


# ── Pre-push hook ─────────────────────────────────────────────────────────────

def test_pre_push_hook_exists() -> None:
    assert PRE_PUSH_PATH.exists(), "pre-push-hook.sh must exist under tools/"


def test_pre_push_hook_has_shebang(pre_push_content: str) -> None:
    assert pre_push_content.startswith("#!/"), (
        "pre-push-hook.sh must start with a shebang"
    )


def test_pre_push_hook_runs_ruff(pre_push_content: str) -> None:
    assert "ruff" in pre_push_content, "pre-push-hook.sh must run ruff"


def test_pre_push_hook_runs_mypy(pre_push_content: str) -> None:
    assert "mypy" in pre_push_content, "pre-push-hook.sh must run mypy"


def test_pre_push_hook_runs_pytest(pre_push_content: str) -> None:
    assert "pytest" in pre_push_content, "pre-push-hook.sh must run pytest"


def test_pre_push_hook_checks_container_running(pre_push_content: str) -> None:
    assert "noa-dev" in pre_push_content, (
        "pre-push-hook.sh must check if noa-dev container is running"
    )


def test_pre_push_hook_container_guard_skips_all_checks(pre_push_content: str) -> None:
    # The container guard must appear BEFORE any docker exec calls so that
    # ruff, mypy, and pytest are all skipped when the container is not running.
    # We look for the docker exec invocations (not comment/shebang mentions).
    guard_idx = pre_push_content.find("docker ps")
    ruff_idx = pre_push_content.find("ruff check")
    mypy_idx = pre_push_content.find("mypy src/")
    # Use the docker exec invocation for pytest to avoid matching comments
    pytest_idx = pre_push_content.find("python -m pytest")
    assert guard_idx != -1, "pre-push-hook.sh must check container via 'docker ps'"
    assert ruff_idx != -1, "pre-push-hook.sh must invoke 'ruff check'"
    assert mypy_idx != -1, "pre-push-hook.sh must invoke 'mypy src/'"
    assert pytest_idx != -1, "pre-push-hook.sh must invoke 'python -m pytest'"
    assert guard_idx < ruff_idx, "container guard must appear before ruff invocation"
    assert guard_idx < mypy_idx, "container guard must appear before mypy invocation"
    assert guard_idx < pytest_idx, (
        "container guard must appear before pytest invocation"
    )


def test_pre_push_hook_exits_nonzero_on_failure(pre_push_content: str) -> None:
    assert "exit 1" in pre_push_content, (
        "pre-push-hook.sh must exit 1 on failure"
    )


def test_pre_push_hook_exits_zero_on_success(pre_push_content: str) -> None:
    assert "exit 0" in pre_push_content, (
        "pre-push-hook.sh must exit 0 on success"
    )


# ── Install hooks script ──────────────────────────────────────────────────────

def test_install_hooks_script_exists() -> None:
    assert INSTALL_HOOKS_PATH.exists(), "install-hooks.sh must exist under tools/"


def test_install_hooks_copies_pre_push() -> None:
    content = INSTALL_HOOKS_PATH.read_text()
    assert "pre-push" in content, "install-hooks.sh must install the pre-push hook"


def test_install_hooks_makes_executable() -> None:
    content = INSTALL_HOOKS_PATH.read_text()
    assert "chmod +x" in content, "install-hooks.sh must chmod +x the hook"
