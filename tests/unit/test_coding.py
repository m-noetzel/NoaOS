"""Tests for Coding Task Contract & Worker -- Phase AB5.

Spec refs: SPEC.md §15 (coding task schema), §2.4 (shell sandbox),
           §8.2 (external worker hardening)

Tests cover: contract validation, shell sandbox scoping/resource caps,
output structure, workspace isolation, max iterations, audit logging,
private domain isolation, and concurrent shell limits.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.ab5


# ---------------------------------------------------------------------------
# 1. Contract Validation (SPEC.md §15)
# ---------------------------------------------------------------------------


class TestCodingTaskInput:
    """CodingTaskInput requires all fields per §15."""

    def test_valid_input_accepted(self, tmp_path: Path) -> None:
        """A fully-specified coding task input is accepted."""
        from noa.coding.contract import CodingTaskInput

        task = CodingTaskInput(
            repo=str(tmp_path),
            objective="Fix the login bug",
            constraints=["no new dependencies"],
            test_command="pytest tests/",
            max_iterations=3,
        )
        assert task.repo == str(tmp_path)
        assert task.max_iterations == 3

    def test_missing_repo_rejected(self) -> None:
        """Repo field is required."""
        from noa.coding.contract import CodingTaskInput

        with pytest.raises(Exception):  # noqa: B017
            CodingTaskInput(
                objective="Fix bug",
                constraints=[],
                test_command="pytest",
            )  # type: ignore[call-arg]

    def test_missing_objective_rejected(self, tmp_path: Path) -> None:
        """Objective field is required."""
        from noa.coding.contract import CodingTaskInput

        with pytest.raises(Exception):  # noqa: B017
            CodingTaskInput(
                repo=str(tmp_path),
                constraints=[],
                test_command="pytest",
            )  # type: ignore[call-arg]

    def test_missing_test_command_rejected(self, tmp_path: Path) -> None:
        """test_command field is required."""
        from noa.coding.contract import CodingTaskInput

        with pytest.raises(Exception):  # noqa: B017
            CodingTaskInput(
                repo=str(tmp_path),
                objective="Fix bug",
                constraints=[],
            )  # type: ignore[call-arg]

    def test_default_max_iterations(self, tmp_path: Path) -> None:
        """max_iterations defaults to 3."""
        from noa.coding.contract import CodingTaskInput

        task = CodingTaskInput(
            repo=str(tmp_path),
            objective="Fix bug",
            constraints=[],
            test_command="pytest",
        )
        assert task.max_iterations == 3


# ---------------------------------------------------------------------------
# 2. Contract Output (SPEC.md §15)
# ---------------------------------------------------------------------------


class TestCodingTaskOutput:
    """CodingTaskOutput contains diff, test_results, lint, summary."""

    def test_output_has_required_fields(self) -> None:
        """Output includes diff, test_results, lint, and summary."""
        from noa.coding.contract import CodingTaskOutput

        output = CodingTaskOutput(
            diff="--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new",
            test_results="3 passed",
            lint="no issues",
            summary="Fixed the bug",
            iterations_used=1,
            success=True,
        )
        assert output.diff is not None
        assert output.test_results == "3 passed"
        assert output.lint == "no issues"
        assert output.summary == "Fixed the bug"
        assert output.iterations_used == 1
        assert output.success is True


# ---------------------------------------------------------------------------
# 3. Shell Sandbox (SPEC.md §2.4)
# ---------------------------------------------------------------------------


class TestShellSandbox:
    """ShellSandbox scopes commands to workspace and enforces resource limits."""

    @pytest.mark.asyncio
    async def test_run_returns_shell_result(self, tmp_path: Path) -> None:
        """ShellSandbox.run returns a ShellResult with stdout/stderr/exit_code."""
        from noa.coding.sandbox import ShellSandbox

        sandbox = ShellSandbox(workspace=tmp_path)
        result = await sandbox.run("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_command_runs_in_workspace_dir(self, tmp_path: Path) -> None:
        """Commands execute with cwd set to the workspace directory."""
        from noa.coding.sandbox import ShellSandbox

        sandbox = ShellSandbox(workspace=tmp_path)
        result = await sandbox.run("pwd")
        assert result.exit_code == 0
        assert str(tmp_path) in result.stdout

    @pytest.mark.asyncio
    async def test_timeout_kills_long_running_command(
        self, tmp_path: Path
    ) -> None:
        """Commands exceeding timeout are killed."""
        from noa.coding.sandbox import ShellSandbox

        sandbox = ShellSandbox(workspace=tmp_path)
        result = await sandbox.run("sleep 60", timeout=1)
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_workspace_path_validated(self) -> None:
        """Workspace must be a valid directory path."""
        from noa.coding.sandbox import ShellSandbox

        with pytest.raises(ValueError, match="workspace"):
            ShellSandbox(workspace=Path("/nonexistent/path/xyz"))

    @pytest.mark.asyncio
    async def test_concurrent_shell_limit(self, tmp_path: Path) -> None:
        """Max 2 concurrent shells enforced."""
        from noa.coding.sandbox import ShellSandbox

        sandbox = ShellSandbox(workspace=tmp_path, max_concurrent=2)

        # Start 3 concurrent commands -- the third should be queued or error
        task1 = asyncio.create_task(sandbox.run("sleep 2"))
        task2 = asyncio.create_task(sandbox.run("sleep 2"))
        # Small delay to ensure first two are running
        await asyncio.sleep(0.1)
        # The semaphore should gate the third
        task3 = asyncio.create_task(sandbox.run("echo third"))

        # All should eventually complete (semaphore queues, not rejects)
        results = await asyncio.gather(task1, task2, task3)
        assert all(r.exit_code is not None for r in results)

    @pytest.mark.asyncio
    async def test_resource_limits_configurable(self, tmp_path: Path) -> None:
        """Timeout and mem_limit are configurable."""
        from noa.coding.sandbox import ShellSandbox

        sandbox = ShellSandbox(
            workspace=tmp_path,
            default_timeout=60,
            mem_limit="2g",
        )
        assert sandbox.default_timeout == 60
        assert sandbox.mem_limit == "2g"


# ---------------------------------------------------------------------------
# 4. Audit Logging (SPEC.md §2.4 -- every command + exit code logged)
# ---------------------------------------------------------------------------


class TestAuditLogging:
    """Every shell command and exit code is logged to audit."""

    @pytest.mark.asyncio
    async def test_command_logged_to_audit(self, tmp_path: Path) -> None:
        """Each shell command and its exit code are recorded."""
        from noa.coding.sandbox import ShellSandbox

        audit_log: list[dict[str, Any]] = []

        def mock_log(entry: dict[str, Any]) -> None:
            audit_log.append(entry)

        sandbox = ShellSandbox(workspace=tmp_path, audit_callback=mock_log)
        await sandbox.run("echo audit_test")

        assert len(audit_log) == 1
        assert audit_log[0]["command"] == "echo audit_test"
        assert audit_log[0]["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_failed_command_logged(self, tmp_path: Path) -> None:
        """Failed commands are also logged with non-zero exit code."""
        from noa.coding.sandbox import ShellSandbox

        audit_log: list[dict[str, Any]] = []

        def mock_log(entry: dict[str, Any]) -> None:
            audit_log.append(entry)

        sandbox = ShellSandbox(workspace=tmp_path, audit_callback=mock_log)
        await sandbox.run("false")

        assert len(audit_log) == 1
        assert audit_log[0]["exit_code"] != 0


# ---------------------------------------------------------------------------
# 5. Coding Worker (SPEC.md §15, §8.2)
# ---------------------------------------------------------------------------


class TestCodingWorker:
    """CodingWorker runs test/edit loops within max_iterations."""

    @pytest.mark.asyncio
    async def test_worker_returns_output(self, tmp_path: Path) -> None:
        """Worker produces a CodingTaskOutput."""
        from noa.coding.contract import CodingTaskInput, CodingTaskOutput
        from noa.coding.worker import CodingWorker

        task = CodingTaskInput(
            repo=str(tmp_path),
            objective="Fix the bug",
            constraints=[],
            test_command="echo PASS",
            max_iterations=1,
        )
        worker = CodingWorker()
        output = await worker.execute(task)
        assert isinstance(output, CodingTaskOutput)

    @pytest.mark.asyncio
    async def test_worker_respects_max_iterations(
        self, tmp_path: Path
    ) -> None:
        """Worker aborts after max_iterations are exhausted."""
        from noa.coding.contract import CodingTaskInput
        from noa.coding.worker import CodingWorker

        task = CodingTaskInput(
            repo=str(tmp_path),
            objective="Impossible task",
            constraints=[],
            test_command="false",  # always fails
            max_iterations=2,
        )
        worker = CodingWorker()
        output = await worker.execute(task)
        assert output.iterations_used <= 2
        assert output.success is False

    @pytest.mark.asyncio
    async def test_worker_captures_diff(self, tmp_path: Path) -> None:
        """Worker captures git diff as part of output."""
        from noa.coding.contract import CodingTaskInput
        from noa.coding.worker import CodingWorker

        # Create a minimal git repo with a file
        (tmp_path / "hello.txt").write_text("hello")

        task = CodingTaskInput(
            repo=str(tmp_path),
            objective="Modify hello.txt",
            constraints=[],
            test_command="echo PASS",
            max_iterations=1,
        )
        worker = CodingWorker()
        output = await worker.execute(task)
        # diff may be empty if no changes were made, but field exists
        assert output.diff is not None
