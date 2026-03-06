"""Pre-flight checks for Noa deployment.

Validates environment variables, Docker prerequisites, and volume setup
before starting the Noa stack. Reference: SPEC.md §30, §31.

Usage:
    python scripts/preflight.py
"""

from __future__ import annotations

import os
import subprocess
import sys

REQUIRED_ENV_VARS: list[str] = [
    "DATABASE_URL",
    "JWT_SECRET",
    "BACKUP_PASSPHRASE",
]

OPTIONAL_ENV_VARS: list[str] = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_AI_API_KEY",
]

EXPECTED_VOLUMES: list[str] = [
    "postgres-data",
    "private-data",
    "backups",
]


def check_env_vars() -> list[str]:
    """Check that all required environment variables are set.

    Returns a list of error messages (empty if all OK).
    """
    errors: list[str] = []
    for var in REQUIRED_ENV_VARS:
        if not os.environ.get(var):
            errors.append(f"Required environment variable {var} is not set")

    for var in OPTIONAL_ENV_VARS:
        if not os.environ.get(var):
            print(f"WARN: Optional variable {var} is not set")

    return errors


def check_docker() -> list[str]:
    """Check that Docker and Docker Compose v2 are available.

    Returns a list of error messages (empty if all OK).
    """
    errors: list[str] = []
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            errors.append(
                f"'docker compose version' failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
    except FileNotFoundError:
        errors.append("Docker is not installed or not on PATH")
    except subprocess.TimeoutExpired:
        errors.append("'docker compose version' timed out")

    return errors


def check_volumes() -> list[str]:
    """Check that expected Docker volumes exist.

    Returns a list of error messages (empty if all OK).
    Volumes are matched by suffix since Compose may prefix with project name.
    """
    errors: list[str] = []
    try:
        result = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            errors.append(f"Failed to list Docker volumes: {result.stderr.strip()}")
            return errors

        existing = result.stdout.strip().splitlines()
        for vol in EXPECTED_VOLUMES:
            if not any(v.endswith(vol) for v in existing):
                errors.append(
                    f"Docker volume '*{vol}' not found. "
                    f"Run 'docker compose up' to create it."
                )
    except FileNotFoundError:
        errors.append("Docker is not installed or not on PATH")
    except subprocess.TimeoutExpired:
        errors.append("'docker volume ls' timed out")

    return errors


def run_preflight() -> tuple[bool, list[str]]:
    """Run all pre-flight checks.

    Returns (pass, errors) where pass is True if no errors.
    """
    all_errors: list[str] = []
    all_errors.extend(check_env_vars())
    all_errors.extend(check_docker())
    all_errors.extend(check_volumes())
    return (len(all_errors) == 0, all_errors)


if __name__ == "__main__":
    ok, errors = run_preflight()
    for e in errors:
        print(f"FAIL: {e}")
    if ok:
        print("All pre-flight checks passed")
    sys.exit(0 if ok else 1)
