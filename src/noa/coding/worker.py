"""Coding task worker per SPEC.md §15, §8.2.

Runs an iterative test-edit loop within the sandbox, capturing
diff, test results, lint output, and a summary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from noa.coding.contract import CodingTaskInput, CodingTaskOutput
from noa.coding.sandbox import ShellSandbox


class CodingWorker:
    """Worker that executes a coding task within a shell sandbox.

    The worker runs the test command up to max_iterations times.
    On each iteration it checks if tests pass. If they do, the task
    is considered successful. Otherwise it continues until exhausted.

    This is the minimal contract implementation; actual code generation
    (LLM-driven edits) would be plugged in at a higher layer.
    """

    def __init__(
        self,
        *,
        audit_callback: Any | None = None,
    ) -> None:
        self._audit_callback = audit_callback

    async def execute(self, task: CodingTaskInput) -> CodingTaskOutput:
        """Execute a coding task.

        Args:
            task: The coding task input with repo, objective, etc.

        Returns:
            CodingTaskOutput with diff, test_results, lint, summary.
        """
        workspace = Path(task.repo)
        sandbox = ShellSandbox(
            workspace=workspace,
            audit_callback=self._audit_callback,
        )

        test_results = ""
        success = False
        iterations_used = 0

        for i in range(task.max_iterations):
            iterations_used = i + 1
            result = await sandbox.run(task.test_command)
            test_results = result.stdout + result.stderr
            if result.exit_code == 0:
                success = True
                break

        # Capture diff (git diff if available, otherwise empty)
        diff_result = await sandbox.run("git diff 2>/dev/null || true")
        diff = diff_result.stdout

        # Capture lint (best-effort)
        lint_result = await sandbox.run("echo 'no lint configured'")
        lint = lint_result.stdout.strip()

        summary = (
            f"Task {'succeeded' if success else 'failed'} "
            f"after {iterations_used} iteration(s). "
            f"Objective: {task.objective}"
        )

        return CodingTaskOutput(
            diff=diff,
            test_results=test_results,
            lint=lint,
            summary=summary,
            iterations_used=iterations_used,
            success=success,
        )
