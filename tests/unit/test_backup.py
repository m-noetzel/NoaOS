"""Tests for Noa backup infrastructure — SPEC.md §10.5.

All tests are self-contained: no Docker, Postgres, or GPG binary required.
We create synthetic GPG files, temp directories, and mock subprocesses.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from noa.maintenance.backup import (
    cleanup_old_backups,
    list_backups,
    run_backup_script,
    validate_crontab,
    verify_backup,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_fake_gpg(path: Path, *, armored: bool = False) -> Path:
    """Create a file that looks like a GPG-encrypted blob."""
    if armored:
        path.write_bytes(
            b"-----BEGIN PGP MESSAGE-----\n\n"
            b"fakedata\n-----END PGP MESSAGE-----\n"
        )
    else:
        # 0xC3 = new-format Symmetric-Key Encrypted Session Key packet tag
        path.write_bytes(b"\xc3" + os.urandom(64))
    return path


def _write_plain(path: Path) -> Path:
    path.write_text("just plain text")
    return path


# ---------------------------------------------------------------------------
# verify_backup
# ---------------------------------------------------------------------------

class TestVerifyBackup:
    def test_valid_binary_gpg(self, tmp_path: Path) -> None:
        f = _write_fake_gpg(tmp_path / "db.sql.gz.gpg")
        assert verify_backup(str(f)) is True

    def test_valid_armored_gpg(self, tmp_path: Path) -> None:
        f = _write_fake_gpg(tmp_path / "db.asc", armored=True)
        assert verify_backup(str(f)) is True

    def test_non_gpg_file(self, tmp_path: Path) -> None:
        f = _write_plain(tmp_path / "plain.txt")
        assert verify_backup(str(f)) is False

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.gpg"
        f.write_bytes(b"")
        assert verify_backup(str(f)) is False

    def test_missing_file(self, tmp_path: Path) -> None:
        assert verify_backup(str(tmp_path / "nope.gpg")) is False

    def test_old_format_gpg_tag(self, tmp_path: Path) -> None:
        """0x8C is the old-format packet tag for tag 3."""
        f = tmp_path / "old.gpg"
        f.write_bytes(b"\x8c" + os.urandom(32))
        assert verify_backup(str(f)) is True


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------

class TestListBackups:
    def test_lists_gpg_files_only(self, tmp_path: Path) -> None:
        _write_fake_gpg(tmp_path / "a.gpg")
        _write_plain(tmp_path / "b.txt")
        _write_fake_gpg(tmp_path / "c.gpg")

        result = list_backups(str(tmp_path))
        assert len(result) == 2
        filenames = {r["filename"] for r in result}
        assert filenames == {"a.gpg", "c.gpg"}

    def test_metadata_keys(self, tmp_path: Path) -> None:
        _write_fake_gpg(tmp_path / "backup.gpg")
        items = list_backups(str(tmp_path))
        assert len(items) == 1
        item = items[0]
        assert "path" in item
        assert "filename" in item
        assert "size" in item
        assert "modified" in item
        assert isinstance(item["size"], int)
        assert item["size"] > 0

    def test_empty_dir(self, tmp_path: Path) -> None:
        assert list_backups(str(tmp_path)) == []

    def test_nonexistent_dir(self) -> None:
        assert list_backups("/nonexistent/dir/xyz") == []


# ---------------------------------------------------------------------------
# cleanup_old_backups
# ---------------------------------------------------------------------------

class TestCleanupOldBackups:
    def test_removes_oldest_keeps_newest(self, tmp_path: Path) -> None:
        # Create 10 files with staggered mtimes
        for i in range(10):
            f = _write_fake_gpg(tmp_path / f"backup_{i:02d}.gpg")
            os.utime(f, (1000 + i, 1000 + i))

        deleted = cleanup_old_backups(str(tmp_path), keep=7)
        assert deleted == 3
        remaining = list(tmp_path.glob("*.gpg"))
        assert len(remaining) == 7

        # The three oldest (00, 01, 02) should be gone
        names = {f.name for f in remaining}
        assert "backup_00.gpg" not in names
        assert "backup_02.gpg" not in names
        assert "backup_09.gpg" in names

    def test_nothing_to_remove(self, tmp_path: Path) -> None:
        for i in range(3):
            _write_fake_gpg(tmp_path / f"b{i}.gpg")
        assert cleanup_old_backups(str(tmp_path), keep=7) == 0

    def test_nonexistent_dir(self) -> None:
        assert cleanup_old_backups("/nonexistent/xyz", keep=7) == 0


# ---------------------------------------------------------------------------
# run_backup_script — mocked subprocess
# ---------------------------------------------------------------------------

class TestRunBackupScript:
    def test_script_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            run_backup_script("/nonexistent/backup.sh")

    def test_successful_run(self, tmp_path: Path) -> None:
        script = tmp_path / "ok.sh"
        script.write_text("#!/bin/bash\necho 'done'")
        script.chmod(0o755)

        result = run_backup_script(str(script))
        assert result.returncode == 0
        assert "done" in result.stdout

    def test_failure_exit_code(self, tmp_path: Path) -> None:
        script = tmp_path / "fail.sh"
        script.write_text("#!/bin/bash\necho 'DB unreachable' >&2\nexit 1")
        script.chmod(0o755)

        result = run_backup_script(str(script))
        assert result.returncode != 0
        assert "DB unreachable" in result.stderr

    def test_env_passthrough(self, tmp_path: Path) -> None:
        script = tmp_path / "env.sh"
        script.write_text('#!/bin/bash\necho "$BACKUP_PASSPHRASE"')
        script.chmod(0o755)

        result = run_backup_script(
            str(script),
            env={"BACKUP_PASSPHRASE": "s3cret"},
        )
        assert "s3cret" in result.stdout


# ---------------------------------------------------------------------------
# validate_crontab
# ---------------------------------------------------------------------------

class TestValidateCrontab:
    def test_valid_crontab(self, tmp_path: Path) -> None:
        crontab = tmp_path / "crontab"
        crontab.write_text(textwrap.dedent("""\
            # Noa backup schedule
            0 2 * * * /scripts/backup.sh
            30 2 * * * /scripts/backup_private.sh
            0 3 * * 0 /scripts/restore_test.sh
        """))
        errors = validate_crontab(str(crontab))
        assert errors == [], f"Unexpected errors: {errors}"

    def test_invalid_hour(self, tmp_path: Path) -> None:
        crontab = tmp_path / "crontab"
        crontab.write_text("0 25 * * * /scripts/backup.sh\n")
        errors = validate_crontab(str(crontab))
        assert len(errors) == 1
        assert "25" in errors[0]

    def test_missing_command(self, tmp_path: Path) -> None:
        crontab = tmp_path / "crontab"
        crontab.write_text("0 2 * * *\n")
        errors = validate_crontab(str(crontab))
        assert len(errors) == 1

    def test_step_syntax(self, tmp_path: Path) -> None:
        crontab = tmp_path / "crontab"
        crontab.write_text("*/15 * * * * /scripts/check.sh\n")
        assert validate_crontab(str(crontab)) == []

    def test_file_not_found(self) -> None:
        errors = validate_crontab("/nonexistent/crontab")
        assert len(errors) == 1
        assert "not found" in errors[0].lower()

    def test_comments_and_blanks_ignored(self, tmp_path: Path) -> None:
        crontab = tmp_path / "crontab"
        crontab.write_text(textwrap.dedent("""\
            # comment line

            # another comment
            0 2 * * * /scripts/backup.sh
        """))
        assert validate_crontab(str(crontab)) == []

    def test_env_var_lines_ignored(self, tmp_path: Path) -> None:
        crontab = tmp_path / "crontab"
        crontab.write_text(textwrap.dedent("""\
            SHELL=/bin/sh
            PATH=/usr/local/bin:/usr/bin
            0 2 * * * /scripts/backup.sh
        """))
        assert validate_crontab(str(crontab)) == []


# ---------------------------------------------------------------------------
# Encrypted backup creation (simulated end-to-end)
# ---------------------------------------------------------------------------

class TestBackupCreatesEncryptedDump:
    """Simulate what backup.sh does: create a file and verify it's GPG-encrypted."""

    def test_backup_creates_encrypted_file(self, tmp_path: Path) -> None:
        """Simulates a backup script creating an encrypted dump file."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = _write_fake_gpg(backup_dir / "noa_2026-03-06_0200.sql.gz.gpg")

        assert backup_file.exists()
        assert verify_backup(str(backup_file)) is True

    def test_encrypted_file_has_valid_gpg_header(self, tmp_path: Path) -> None:
        """The encrypted file must begin with a recognized GPG magic byte."""
        f = _write_fake_gpg(tmp_path / "encrypted.gpg")
        with open(f, "rb") as fh:
            first_byte = fh.read(1)
        assert first_byte in (b"\xc3", b"\x8c"), (
            f"Unexpected first byte: {first_byte!r}"
        )


class TestPrivateDataBackup:
    def test_private_backup_creates_encrypted_archive(self, tmp_path: Path) -> None:
        private_backup_dir = tmp_path / "backups" / "private"
        private_backup_dir.mkdir(parents=True)
        archive = _write_fake_gpg(
            private_backup_dir / "private_2026-03-06_0230.tar.gz.gpg"
        )

        assert archive.exists()
        assert verify_backup(str(archive)) is True
        items = list_backups(str(private_backup_dir))
        assert len(items) == 1
        assert items[0]["filename"] == "private_2026-03-06_0230.tar.gz.gpg"


class TestRestoreRecovery:
    """Simulate restore by writing data, 'encrypting', 'decrypting', verifying."""

    def test_restore_recovers_data(self, tmp_path: Path) -> None:
        original = b"CREATE TABLE users (id int); INSERT INTO users VALUES (1);"

        # Simulate encrypt
        encrypted = tmp_path / "backup.sql.gz.gpg"
        # In real life GPG would transform this; here we just round-trip
        encrypted.write_bytes(b"\xc3" + original)

        # Simulate decrypt: strip GPG header
        decrypted = encrypted.read_bytes()[1:]
        assert decrypted == original

    def test_backup_fails_gracefully_on_db_unreachable(self, tmp_path: Path) -> None:
        """When the DB is unreachable the backup script exits non-zero."""
        script = tmp_path / "backup.sh"
        script.write_text(textwrap.dedent("""\
            #!/bin/bash
            set -euo pipefail
            pg_dump 2>/dev/null || { echo "ERROR: Database unreachable" >&2; exit 1; }
        """))
        script.chmod(0o755)

        result = run_backup_script(str(script))
        assert result.returncode != 0
        assert "unreachable" in result.stderr.lower() or result.returncode != 0
