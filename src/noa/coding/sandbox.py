"""Shell sandbox execution per SPEC.md §2.4.

Provides workspace-scoped shell execution with resource limits,
concurrency control, and audit logging.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ShellResult:
    """Result of a shell command execution."""

    stdout: str
    stderr: str
    exit_code: int


class ShellSandbox:
    """Workspace-scoped shell sandbox (§2.4).

    Commands are executed with cwd set to the workspace directory.
    Resource limits (timeout, memory) are enforced.
    A semaphore gates concurrent shell execution.
    Every command and exit code is logged via the audit callback.

    Args:
        workspace: Path to the workspace directory. Must exist.
        max_concurrent: Maximum number of concurrent shell processes.
        default_timeout: Default timeout in seconds for commands.
        mem_limit: Memory limit string (e.g. "4g"). Informational for
            container-level enforcement; not enforced in-process.
        audit_callback: Optional callback invoked with a dict for each
            command execution (command, exit_code, stdout, stderr).
    """

    def __init__(
        self,
        workspace: Path,
        *,
        max_concurrent: int = 2,
        default_timeout: int = 300,
        mem_limit: str = "4g",
        audit_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if not workspace.is_dir():
            raise ValueError(f"workspace must be an existing directory: {workspace}")
        self._workspace = workspace
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.default_timeout = default_timeout
        self.mem_limit = mem_limit
        self._audit_callback = audit_callback

    async def run(
        self,
        cmd: str,
        *,
        timeout: int | None = None,
    ) -> ShellResult:
        """Execute a shell command in the workspace.

        Args:
            cmd: Shell command string to execute.
            timeout: Timeout in seconds. Defaults to self.default_timeout.

        Returns:
            ShellResult with stdout, stderr, and exit_code.
        """
        effective_timeout = timeout if timeout is not None else self.default_timeout

        async with self._semaphore:
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self._workspace),
                )
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=effective_timeout,
                )
                exit_code = proc.returncode if proc.returncode is not None else -1
                stdout = stdout_bytes.decode(errors="replace")
                stderr = stderr_bytes.decode(errors="replace")
            except TimeoutError:
                # Kill the process on timeout
                try:
                    proc.kill()
                    await proc.wait()
                except (ProcessLookupError, OSError):
                    pass
                stdout = ""
                stderr = "command timed out"
                exit_code = -1

        result = ShellResult(stdout=stdout, stderr=stderr, exit_code=exit_code)

        if self._audit_callback is not None:
            self._audit_callback(
                {
                    "command": cmd,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )

        return result
