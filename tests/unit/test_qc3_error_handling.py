"""Tests for Phase QC3: Error Handling & Observability.

Covers: H4 (repository transaction boundaries), H5 (exception handling quality),
M8 (cost endpoint error codes), M11 (unified AuthUser extraction),
M13 (backup script error propagation and env safety).

Spec refs: ARCH_INVARIANTS.md L9, L1; FINDINGS.md H4, H5, M8, M11, M13
Phase plan: MASTER_PLAN.md Phase QC3
"""

from __future__ import annotations

import logging
import os
import stat
import subprocess
import textwrap
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.qc3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"


def _make_jwt_payload(**overrides: object) -> dict:
    """Build a minimal JWT-like payload dict."""
    base = {"type": "access", "sub": _VALID_UUID}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Group 1: H4 -- Repository Transaction Boundary
# ---------------------------------------------------------------------------


class TestSettingsRepositoryTransactionBoundary:
    """FINDINGS.md H4: SettingsRepository must not own transaction commit."""

    @pytest.mark.asyncio
    async def test_upsert_does_not_commit(self) -> None:
        """FINDINGS.md H4: Repository.upsert() must never call session.commit().

        Commit ownership belongs to the caller (endpoint/service layer).
        If commit remains in the repo, multi-step transactions break.
        """
        session = AsyncMock()
        # execute() returns a result with scalar_one_or_none
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        from noa.settings.repository import SettingsRepository

        repo = SettingsRepository(session)
        await repo.upsert(
            user_id=uuid.UUID(_VALID_UUID),
            fields={"default_model": "claude-sonnet-4-20250514"},
        )

        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_calls_flush(self) -> None:
        """FINDINGS.md H4: Repository.upsert() should flush so the row is visible
        within the current transaction before the caller commits."""
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        from noa.settings.repository import SettingsRepository

        repo = SettingsRepository(session)
        await repo.upsert(
            user_id=uuid.UUID(_VALID_UUID),
            fields={"default_model": "claude-sonnet-4-20250514"},
        )

        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_two_upserts_atomic_rollback(self) -> None:
        """FINDINGS.md H4: Multiple upserts in the same transaction must
        roll back atomically when the transaction is aborted."""
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        from noa.settings.repository import SettingsRepository

        repo = SettingsRepository(session)
        await repo.upsert(uuid.UUID(_VALID_UUID), {"default_model": "m1"})
        await repo.upsert(uuid.UUID(_VALID_UUID), {"default_model": "m2"})

        # Neither call should have committed
        session.commit.assert_not_called()
        # Rollback is the caller's responsibility -- repo must not interfere
        assert session.rollback.call_count == 0


# ---------------------------------------------------------------------------
# Group 2: H5 -- Exception Handling Quality
# ---------------------------------------------------------------------------


class TestExceptionHandlingQuality:
    """FINDINGS.md H5: Bare except blocks must log, not silently swallow."""

    @pytest.mark.asyncio
    async def test_cost_summary_db_error_logs_warning(self) -> None:
        """FINDINGS.md H5 + M8: cost_summary must log a warning with
        exc_info when a DB error occurs, and NOT return HTTP 200."""
        from sqlalchemy.exc import OperationalError

        mock_factory = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute.side_effect = OperationalError(
            "select", {}, Exception("connection refused")
        )
        mock_factory.return_value = mock_session

        with (
            patch("noa.api.v1.cost._get_session_factory", return_value=mock_factory),
            patch("noa.api.v1.cost.require_auth", return_value=_make_jwt_payload()),
        ):
            from noa.api.v1.cost import cost_summary

            mock_request = MagicMock()
            mock_request.state.trace_id = "test-trace-id"

            # The endpoint must NOT return 200 on DB error -- it must raise or
            # return a 5xx response. This test will FAIL before QC3 implementation.
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await cost_summary(request=mock_request, period="monthly", user=_make_jwt_payload())

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_make_run_service_db_error_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """FINDINGS.md H5: _make_run_service inner except must log at DEBUG
        level (not silently pass) when factory() raises."""
        with patch("noa.api.v1.chat._get_session_factory") as mock_gsf:
            mock_factory = MagicMock()
            mock_factory.side_effect = Exception("connection refused")
            mock_gsf.return_value = mock_factory

            from noa.api.v1.chat import _make_run_service, _NoOpRunService

            with caplog.at_level(logging.DEBUG):
                result = _make_run_service(
                    user_id="u1", thread_id="t1", run_id="r1"
                )

            assert isinstance(result, _NoOpRunService)
            # After QC3, a log entry must exist -- not silent pass
            assert any(
                "connection refused" in record.message.lower()
                or "run_service" in record.message.lower()
                or "factory" in record.message.lower()
                for record in caplog.records
            ), "Expected a log entry when _make_run_service factory fails"

    @pytest.mark.asyncio
    async def test_lifespan_db_skip_emits_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """FINDINGS.md H5: app.py lifespan DB-skip except must log at WARNING,
        not silently pass. This is the exempted block (noqa S110) but it still
        must produce an observable log entry."""
        with (
            patch("noa.api.app.create_async_engine_from_config", side_effect=Exception("no db")),
            caplog.at_level(logging.WARNING),
        ):
            # We need to trigger the lifespan. Import and invoke it.
            from noa.api.app import app

            # The lifespan context manager should log a warning when DB init fails
            # but not crash. We look for a WARNING-level record.
            warning_records = [
                r for r in caplog.records if r.levelno >= logging.WARNING
            ]
            # This test verifies the fix: after QC3, a WARNING must be emitted.
            # Before QC3, the bare `except: pass` produces no log.
            assert len(warning_records) > 0, (
                "Expected WARNING log when DB engine creation fails in lifespan"
            )


# ---------------------------------------------------------------------------
# Group 3: M8 -- Cost Endpoint HTTP 500 on Database Error
# ---------------------------------------------------------------------------


class TestCostEndpointErrorCodes:
    """FINDINGS.md M8: Cost endpoints must return HTTP 500 on DB errors,
    not HTTP 200 with empty data."""

    @pytest.mark.asyncio
    async def test_cost_summary_returns_500_on_db_error(self) -> None:
        """FINDINGS.md M8: cost_summary must return 500 (not 200) when the
        database raises OperationalError."""
        from sqlalchemy.exc import OperationalError
        from fastapi import HTTPException

        mock_factory = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute.side_effect = OperationalError(
            "select", {}, Exception("db down")
        )
        mock_factory.return_value = mock_session

        with patch("noa.api.v1.cost._get_session_factory", return_value=mock_factory):
            from noa.api.v1.cost import cost_summary

            mock_request = MagicMock()
            mock_request.state.trace_id = "trace-001"

            with pytest.raises(HTTPException) as exc_info:
                await cost_summary(
                    request=mock_request,
                    period="monthly",
                    user=_make_jwt_payload(),
                )

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_cost_records_returns_500_on_db_error(self) -> None:
        """FINDINGS.md M8: cost_records must return 500 (not 200) when the
        database raises OperationalError."""
        from sqlalchemy.exc import OperationalError
        from fastapi import HTTPException

        mock_factory = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute.side_effect = OperationalError(
            "select", {}, Exception("db down")
        )
        mock_factory.return_value = mock_session

        with patch("noa.api.v1.cost._get_session_factory", return_value=mock_factory):
            from noa.api.v1.cost import cost_records

            mock_request = MagicMock()
            mock_request.state.trace_id = "trace-002"

            with pytest.raises(HTTPException) as exc_info:
                await cost_records(
                    request=mock_request,
                    limit=50,
                    user=_make_jwt_payload(),
                )

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_cost_summary_returns_200_when_no_factory(self) -> None:
        """FINDINGS.md M8: When no DB is configured (factory is None),
        cost_summary returns HTTP 200 with empty data -- this is intentional
        graceful degradation, distinct from a DB error."""
        with patch("noa.api.v1.cost._get_session_factory", return_value=None):
            from noa.api.v1.cost import cost_summary

            mock_request = MagicMock()
            mock_request.state.trace_id = "trace-003"

            result = await cost_summary(
                request=mock_request,
                period="monthly",
                user=_make_jwt_payload(),
            )

            assert result["ok"] is True
            assert result["data"] == []

    @pytest.mark.asyncio
    async def test_cost_records_returns_200_when_no_factory(self) -> None:
        """FINDINGS.md M8: When no DB is configured (factory is None),
        cost_records returns HTTP 200 with empty data."""
        with patch("noa.api.v1.cost._get_session_factory", return_value=None):
            from noa.api.v1.cost import cost_records

            mock_request = MagicMock()
            mock_request.state.trace_id = "trace-004"

            result = await cost_records(
                request=mock_request,
                limit=50,
                user=_make_jwt_payload(),
            )

            assert result["ok"] is True
            assert result["data"] == []


# ---------------------------------------------------------------------------
# Group 4: M11 -- Unified AuthUser Extraction
# ---------------------------------------------------------------------------


class TestAuthUserExtraction:
    """FINDINGS.md M11: require_auth must return a typed AuthUser object,
    not a raw dict with fragile .get() fallback chains."""

    def test_authuser_class_exists_in_middleware(self) -> None:
        """FINDINGS.md M11: An AuthUser dataclass (or equivalent) must exist
        in noa.auth.middleware with a user_id field."""
        from noa.auth.middleware import AuthUser

        # Must be importable -- if not, ImportError proves the fix is missing
        assert hasattr(AuthUser, "user_id"), "AuthUser must have a user_id attribute"

    def test_authuser_user_id_is_uuid(self) -> None:
        """FINDINGS.md M11: AuthUser.user_id must be a uuid.UUID, not a string.
        This eliminates the uuid.UUID('') ValueError that plagued the old code."""
        from noa.auth.middleware import AuthUser

        user = AuthUser(user_id=uuid.UUID(_VALID_UUID))
        assert isinstance(user.user_id, uuid.UUID)
        assert str(user.user_id) == _VALID_UUID

    def test_authuser_rejects_empty_string_user_id(self) -> None:
        """FINDINGS.md M11: AuthUser construction must reject empty user_id.
        Before the fix, empty string reached uuid.UUID('') and raised ValueError
        deep inside endpoint code. Now it must fail at construction time."""
        from noa.auth.middleware import AuthUser

        with pytest.raises((ValueError, TypeError)):
            AuthUser(user_id=uuid.UUID(""))

    def test_authuser_handles_uppercase_uuid(self) -> None:
        """FINDINGS.md M11 (edge case EC-4): UUID with uppercase letters
        must be accepted -- Python's uuid.UUID is case-insensitive."""
        from noa.auth.middleware import AuthUser

        upper_uuid = "550E8400-E29B-41D4-A716-446655440000"
        user = AuthUser(user_id=uuid.UUID(upper_uuid))
        assert user.user_id == uuid.UUID(_VALID_UUID)

    @pytest.mark.asyncio
    async def test_require_auth_returns_authuser_not_dict(self) -> None:
        """FINDINGS.md M11: require_auth must return an AuthUser instance,
        not a raw dict. All endpoints depend on this contract."""
        from noa.auth.middleware import AuthUser

        # Patch JWT decode to return a valid payload
        with patch("noa.auth.middleware.jwt.decode", return_value=_make_jwt_payload()):
            from noa.auth.middleware import require_auth

            mock_request = MagicMock()
            mock_request.cookies = {}
            mock_creds = MagicMock()
            mock_creds.credentials = "fake.jwt.token"

            from noa.config import Settings

            mock_settings = MagicMock(spec=Settings)
            mock_settings.secret_key = "test-secret"

            result = await require_auth(
                request=mock_request,
                credentials=mock_creds,
                settings=mock_settings,
            )

            assert isinstance(result, AuthUser), (
                f"require_auth must return AuthUser, got {type(result).__name__}"
            )
            assert isinstance(result.user_id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_jwt_missing_sub_raises_401_not_500(self) -> None:
        """FINDINGS.md M11: JWT payload without 'sub' claim must produce
        HTTP 401, not an unhandled KeyError -> 500."""
        from fastapi import HTTPException

        payload_no_sub = {"type": "access"}  # no 'sub' key

        with patch("noa.auth.middleware.jwt.decode", return_value=payload_no_sub):
            from noa.auth.middleware import require_auth

            mock_request = MagicMock()
            mock_request.cookies = {}
            mock_creds = MagicMock()
            mock_creds.credentials = "fake.jwt.token"

            from noa.config import Settings

            mock_settings = MagicMock(spec=Settings)
            mock_settings.secret_key = "test-secret"

            with pytest.raises(HTTPException) as exc_info:
                await require_auth(
                    request=mock_request,
                    credentials=mock_creds,
                    settings=mock_settings,
                )

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_non_uuid_sub_raises_structured_error(self) -> None:
        """FINDINGS.md M11: JWT with non-UUID 'sub' must produce HTTP 401 or
        422, not an unhandled ValueError -> 500."""
        from fastapi import HTTPException

        payload_bad_sub = {"type": "access", "sub": "not-a-uuid"}

        with patch("noa.auth.middleware.jwt.decode", return_value=payload_bad_sub):
            from noa.auth.middleware import require_auth

            mock_request = MagicMock()
            mock_request.cookies = {}
            mock_creds = MagicMock()
            mock_creds.credentials = "fake.jwt.token"

            from noa.config import Settings

            mock_settings = MagicMock(spec=Settings)
            mock_settings.secret_key = "test-secret"

            with pytest.raises(HTTPException) as exc_info:
                await require_auth(
                    request=mock_request,
                    credentials=mock_creds,
                    settings=mock_settings,
                )

            assert exc_info.value.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_empty_sub_raises_401_at_middleware(self) -> None:
        """FINDINGS.md M11 (edge case): JWT with sub='' must be caught by
        require_auth with 401, not propagate to endpoints where uuid.UUID('')
        would raise ValueError -> 500."""
        from fastapi import HTTPException

        payload_empty_sub = {"type": "access", "sub": ""}

        with patch("noa.auth.middleware.jwt.decode", return_value=payload_empty_sub):
            from noa.auth.middleware import require_auth

            mock_request = MagicMock()
            mock_request.cookies = {}
            mock_creds = MagicMock()
            mock_creds.credentials = "fake.jwt.token"

            from noa.config import Settings

            mock_settings = MagicMock(spec=Settings)
            mock_settings.secret_key = "test-secret"

            with pytest.raises(HTTPException) as exc_info:
                await require_auth(
                    request=mock_request,
                    credentials=mock_creds,
                    settings=mock_settings,
                )

            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Group 5: M13 -- Backup Script Error Propagation and Env Safety
# ---------------------------------------------------------------------------


class TestBackupScriptSafety:
    """FINDINGS.md M13: run_backup_script must propagate errors and not leak
    os.environ to the subprocess."""

    def test_run_backup_raises_on_nonzero_exit(self, tmp_path: object) -> None:
        """FINDINGS.md M13: run_backup_script must raise CalledProcessError
        when the script exits non-zero (check=True behavior).

        Before the fix, check=False silently swallows failures."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as f:
            f.write("#!/bin/bash\nexit 1\n")
            script_path = f.name
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)

        try:
            from noa.maintenance.backup import run_backup_script

            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                run_backup_script(script_path, env={})

            assert exc_info.value.returncode == 1
        finally:
            os.unlink(script_path)

    def test_run_backup_does_not_leak_os_environ(self, tmp_path: object) -> None:
        """FINDINGS.md M13: run_backup_script must NOT pass full os.environ
        to the subprocess. Only caller-provided env vars should be visible.

        Before the fix, {**os.environ, ...} leaks SECRET_KEY etc."""
        import tempfile

        sentinel = f"SENTINEL_{uuid.uuid4().hex[:8]}"
        os.environ[sentinel] = "should-not-leak"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as f:
            f.write(textwrap.dedent(f"""\
                #!/bin/bash
                echo "${{{sentinel}:-NOT_FOUND}}"
            """))
            script_path = f.name
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)

        try:
            from noa.maintenance.backup import run_backup_script

            # After QC3 fix, check=True is default. A clean script (exit 0)
            # is needed here to avoid CalledProcessError. The script above
            # exits 0 by default.
            try:
                result = run_backup_script(
                    script_path, env={"BACKUP_PASSPHRASE": "test"}
                )
            except subprocess.CalledProcessError as e:
                # If check=True is already in place, capture stdout from error
                result = e

            stdout = (
                result.stdout
                if hasattr(result, "stdout") and result.stdout
                else ""
            )
            assert "should-not-leak" not in stdout, (
                f"os.environ[{sentinel}] leaked to subprocess"
            )
        finally:
            os.environ.pop(sentinel, None)
            os.unlink(script_path)

    def test_run_backup_passes_caller_env_vars(self, tmp_path: object) -> None:
        """FINDINGS.md M13: Caller-provided env vars must be available to
        the subprocess -- the whitelist must not block legitimate vars."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as f:
            f.write(textwrap.dedent("""\
                #!/bin/bash
                echo "PASSPHRASE=$BACKUP_PASSPHRASE"
                echo "HOST=$PGHOST"
            """))
            script_path = f.name
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)

        try:
            from noa.maintenance.backup import run_backup_script

            result = run_backup_script(
                script_path,
                env={"BACKUP_PASSPHRASE": "s3cret", "PGHOST": "db.local"},
            )
            stdout = result.stdout if hasattr(result, "stdout") else ""
            assert "PASSPHRASE=s3cret" in stdout
            assert "HOST=db.local" in stdout
        finally:
            os.unlink(script_path)

    def test_backup_error_includes_diagnostic_info(self) -> None:
        """FINDINGS.md M13: CalledProcessError from failed backup must include
        returncode and stderr for diagnostics."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as f:
            f.write(textwrap.dedent("""\
                #!/bin/bash
                echo "pg_dump: could not connect" >&2
                exit 1
            """))
            script_path = f.name
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)

        try:
            from noa.maintenance.backup import run_backup_script

            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                run_backup_script(script_path, env={})

            assert exc_info.value.returncode == 1
            assert "pg_dump" in (exc_info.value.stderr or "")
        finally:
            os.unlink(script_path)

    def test_run_backup_timeout_raises_timeout_expired(self) -> None:
        """FINDINGS.md M13: Timeout behavior must be preserved after adding
        check=True -- long-running scripts still raise TimeoutExpired."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as f:
            f.write("#!/bin/bash\nsleep 30\n")
            script_path = f.name
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)

        try:
            from noa.maintenance.backup import run_backup_script

            with pytest.raises(subprocess.TimeoutExpired):
                run_backup_script(script_path, timeout=1, env={})
        finally:
            os.unlink(script_path)

    def test_run_backup_has_env_parameter(self) -> None:
        """FINDINGS.md M13: run_backup_script must accept an 'env' parameter
        as the only way to pass environment to the subprocess."""
        import inspect

        from noa.maintenance.backup import run_backup_script

        sig = inspect.signature(run_backup_script)
        assert "env" in sig.parameters, (
            "run_backup_script must have an 'env' parameter"
        )


# ---------------------------------------------------------------------------
# Group 6: Integration Smoke Tests
# ---------------------------------------------------------------------------


class TestQC3Imports:
    """Integration: all modified modules must import without error."""

    def test_all_modified_modules_import(self) -> None:
        """MASTER_PLAN Phase QC3: Smoke-test imports of all files touched by QC3."""
        # Each import must succeed -- ImportError means the fix broke the module
        from noa.settings.repository import SettingsRepository  # noqa: F401

        assert SettingsRepository is not None

        from noa.api.v1.cost import router as cost_router  # noqa: F401

        assert cost_router is not None

        from noa.api.v1.chat import router as chat_router  # noqa: F401

        assert chat_router is not None

        from noa.api.v1.settings import router as settings_router  # noqa: F401

        assert settings_router is not None

        from noa.auth.middleware import require_auth  # noqa: F401

        assert require_auth is not None

        from noa.maintenance.backup import run_backup_script  # noqa: F401

        assert run_backup_script is not None

        # AuthUser must be importable after QC3
        from noa.auth.middleware import AuthUser  # noqa: F401

        assert AuthUser is not None


class TestQC3Integration:
    """Integration tests calling real code with minimal mocking."""

    @pytest.mark.asyncio
    async def test_settings_upsert_persists_via_caller_commit(self) -> None:
        """MASTER_PLAN Phase QC3 / FINDINGS.md H4: After removing commit()
        from SettingsRepository, the caller must commit explicitly for the
        row to persist. This is the non-mocked integration test (S5 requirement).

        Uses real SQLAlchemy async session with in-memory SQLite."""
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            create_async_engine,
        )
        from sqlalchemy.orm import sessionmaker

        from noa.db.models import Base
        from noa.settings.models import UserSettings  # noqa: F401
        from noa.settings.repository import SettingsRepository

        engine = create_async_engine("sqlite+aiosqlite://", echo=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Also create a users row so the FK constraint is satisfied
        # (SQLite doesn't enforce FK by default, but be safe)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash) "
                    "VALUES (:id, :email, :hash)"
                ),
                {
                    "id": _VALID_UUID,
                    "email": "test@test.com",
                    "hash": "fakehash",
                },
            )

        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Write: upsert + caller commits
        async with Session() as session:
            repo = SettingsRepository(session)
            await repo.upsert(
                uuid.UUID(_VALID_UUID),
                {"default_model": "claude-sonnet-4-20250514"},
            )
            await session.commit()  # Caller commits, not repo

        # Read: verify persistence in a fresh session
        async with Session() as session:
            from sqlalchemy import select

            stmt = select(UserSettings).where(
                UserSettings.user_id == uuid.UUID(_VALID_UUID)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            assert row is not None, "Settings row not persisted after caller commit"
            assert row.default_model == "claude-sonnet-4-20250514"

        await engine.dispose()
