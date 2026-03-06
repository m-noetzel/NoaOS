"""Backup utilities for Noa — SPEC.md §10.5.

Provides helpers for verifying, listing, and managing encrypted backup files
produced by the backup shell scripts (scripts/backup.sh, scripts/backup_private.sh).
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

# GPG symmetric-encrypted files start with these magic bytes.
# 0xC3 = new-format packet tag for Symmetric-Key Encrypted Session Key (tag 3)
# 0x8C = old-format equivalent
_GPG_MAGIC_BYTES = (b"\xc3", b"\x8c")

# Also accept ASCII-armored GPG files
_GPG_ARMOR_HEADER = b"-----BEGIN PGP MESSAGE-----"


def verify_backup(path: str) -> bool:
    """Check whether *path* points to a valid GPG-encrypted file.

    Returns ``True`` when the file exists, is non-empty, and starts with
    a recognised GPG header (binary or ASCII-armored).
    """
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        return False

    with open(p, "rb") as fh:
        header = fh.read(64)

    # Binary GPG
    if header[:1] in _GPG_MAGIC_BYTES:
        return True

    # ASCII-armored GPG
    return bool(header.lstrip().startswith(_GPG_ARMOR_HEADER))


def list_backups(backup_dir: str) -> list[dict[str, object]]:
    """Return metadata for each ``*.gpg`` file in *backup_dir*.

    Each entry is a dict with keys:

    * ``path`` — absolute path string
    * ``filename`` — base filename
    * ``size`` — file size in bytes
    * ``modified`` — last-modified time as an ISO-8601 string (UTC)
    """
    d = Path(backup_dir)
    if not d.is_dir():
        return []

    results: list[dict[str, object]] = []
    for entry in sorted(d.iterdir()):
        if entry.suffix == ".gpg" and entry.is_file():
            stat = entry.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            results.append(
                {
                    "path": str(entry.resolve()),
                    "filename": entry.name,
                    "size": stat.st_size,
                    "modified": mtime.isoformat(),
                }
            )
    return results


def cleanup_old_backups(backup_dir: str, keep: int = 7) -> int:
    """Remove the oldest ``*.gpg`` files in *backup_dir*, keeping *keep* most recent.

    Returns the number of files deleted.
    """
    d = Path(backup_dir)
    if not d.is_dir():
        return 0

    gpg_files = sorted(
        (f for f in d.iterdir() if f.suffix == ".gpg" and f.is_file()),
        key=lambda f: f.stat().st_mtime,
    )

    to_remove = gpg_files[: max(0, len(gpg_files) - keep)]
    for f in to_remove:
        f.unlink()
    return len(to_remove)


def run_backup_script(
    script: str,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    """Execute a backup shell script, returning the CompletedProcess.

    Raises ``subprocess.TimeoutExpired`` if the script exceeds *timeout* seconds.
    Raises ``FileNotFoundError`` if the script does not exist.
    """
    script_path = Path(script)
    if not script_path.is_file():
        raise FileNotFoundError(f"Backup script not found: {script}")

    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(  # noqa: S603
        ["bash", str(script_path)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged_env,
        check=False,
    )


def validate_crontab(crontab_path: str) -> list[str]:
    """Validate crontab syntax and return a list of errors (empty = valid).

    Each non-blank, non-comment line must have 5 time fields followed by a
    command.  The time fields are validated against their allowed ranges.
    """
    errors: list[str] = []
    p = Path(crontab_path)
    if not p.is_file():
        return [f"File not found: {crontab_path}"]

    field_ranges = [
        (0, 59),   # minute
        (0, 23),   # hour
        (1, 31),   # day of month
        (1, 12),   # month
        (0, 7),    # day of week (0 and 7 = Sunday)
    ]

    for lineno, raw_line in enumerate(p.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Handle env var assignments (e.g. SHELL=/bin/sh)
        if re.match(r"^[A-Za-z_][A-Za-z_0-9]*=", line):
            continue

        parts = line.split(None, 5)
        if len(parts) < 6:
            errors.append(
                f"Line {lineno}: expected 5 time fields + command,"
                f" got {len(parts)} fields"
            )
            continue

        for i, (field, (lo, hi)) in enumerate(
            zip(parts[:5], field_ranges, strict=True),
        ):
            if not _valid_cron_field(field, lo, hi):
                errors.append(
                    f"Line {lineno}: invalid cron field"
                    f" {i + 1} '{field}' (range {lo}-{hi})"
                )

    return errors


def _valid_cron_field(field: str, lo: int, hi: int) -> bool:
    """Return True if *field* is a syntactically valid cron time field."""
    if field == "*":
        return True

    # Handle */N step
    if field.startswith("*/"):
        try:
            step = int(field[2:])
            return 1 <= step <= hi
        except ValueError:
            return False

    # Handle comma-separated values
    for part in field.split(","):
        # Range N-M
        if "-" in part:
            pieces = part.split("-", 1)
            try:
                a, b = int(pieces[0]), int(pieces[1])
                if not (lo <= a <= hi and lo <= b <= hi):
                    return False
            except ValueError:
                return False
        else:
            try:
                val = int(part)
                if not (lo <= val <= hi):
                    return False
            except ValueError:
                return False

    return True
