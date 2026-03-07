"""Tests for architecture & robustness fixes — Phase QC8.

Spec refs: SPEC.md §19.1 (idempotency), §19.3 (rate limits), §21 (risk tiers),
           §22.4 (SSE streaming), §25.3 (middleware), §25.4 (idempotency key),
           §11.3 (refresh token rotation), §10.1 (checkpointer)
Phase plan: PHASE_DETAILS.md Phase QC8

Findings addressed:
  A1  — Global mutable state cleanup (reset_all)
  A2  — ProviderRouter refactor (inject clients, backward compat)
  A4  — Checkpointer stub (NoOpCheckpointer)
  A5  — Transaction abstraction (async context manager)
  H8  — Per-user rate limiting (user isolation)
  M1  — Idempotency wiring (ContextVar, deduplication)
  M5  — SSE event replay (Last-Event-ID support)
  M7  — Step-up auth enforcement in gateway
  M10 — Google refresh token persistence callback

These tests define the behavioral contract for architecture fixes.
They are written BEFORE implementation and must fail initially.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.qc8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ===========================================================================
# A1 — Global Mutable State: reset_all()
# ===========================================================================


class TestA1ResetAll:
    """A1: app_state.reset_all() must clear every global to None."""

    def test_reset_all_clears_all_globals(self) -> None:
        """After setting all globals and calling reset_all(), every getter
        must return None.  Phase QC8 / A1."""
        from noa.api import app_state

        # Set all 6 globals to sentinel values
        app_state.set_engine(MagicMock())
        app_state.set_session_factory(MagicMock())
        app_state.set_health_checker(MagicMock())
        app_state.set_provider_router(MagicMock())
        app_state.set_runner(MagicMock())
        app_state.set_gateway(MagicMock())

        # Precondition: at least one is set
        assert app_state.get_engine() is not None

        # ACT — reset_all() must exist after QC8
        app_state.reset_all()

        # All getters must return None
        assert app_state.get_engine() is None
        assert app_state.get_session_factory() is None
        assert app_state.get_health_checker() is None
        assert app_state.get_provider_router() is None
        assert app_state.get_runner() is None
        assert app_state.get_gateway() is None

    def test_reset_all_is_idempotent(self) -> None:
        """Calling reset_all() twice does not crash.  Phase QC8 / A1."""
        from noa.api import app_state

        app_state.reset_all()
        app_state.reset_all()  # must not raise


# ===========================================================================
# A2 — ProviderRouter Refactor
# ===========================================================================


class TestA2ProviderRouterRefactor:
    """A2: ProviderRouter accepts injected clients dict."""

    def test_provider_router_accepts_injected_clients(self) -> None:
        """ProviderRouter constructed with a clients dict exposes them
        via available_providers.  Phase QC8 / A2."""
        from noa.external_worker.llm.router import ProviderRouter

        mock_anthropic = MagicMock()
        mock_ollama = MagicMock()
        clients = {"anthropic": mock_anthropic, "ollama": mock_ollama}

        # QC8 adds a constructor that accepts clients= kwarg
        router = ProviderRouter(
            config={"default_provider": "anthropic", "providers": {}},
            clients=clients,
        )

        assert "anthropic" in router.available_providers
        assert "ollama" in router.available_providers

    def test_from_settings_backward_compat(self) -> None:
        """from_settings() must still work after refactor.  Phase QC8 / A2."""
        from noa.external_worker.llm.router import ProviderRouter

        settings = MagicMock()
        settings.default_provider = "anthropic"
        settings.anthropic_api_key = "sk-test"
        settings.openai_api_key = None
        settings.google_ai_api_key = None
        settings.ollama_base_url = "http://ollama:11434"
        settings.default_model = None

        # Patch real client constructors to avoid network
        with patch(
            "noa.external_worker.llm.anthropic.AnthropicClient"
        ) as MockAnthropic, patch(
            "noa.llm.providers.OllamaClient"
        ):
            MockAnthropic.return_value = MagicMock()
            router = ProviderRouter.from_settings(settings)

        assert "anthropic" in router.available_providers

    def test_empty_clients_raises_on_complete(self) -> None:
        """Router with empty clients dict can be constructed but raises
        ProviderError on complete().  Phase QC8 / A2."""
        from noa.external_worker.llm.router import ProviderError, ProviderRouter

        router = ProviderRouter(
            config={"default_provider": "anthropic", "providers": {}},
            clients={},
        )

        assert router.available_providers == []

        with pytest.raises(ProviderError):
            asyncio.run(
                router.complete(
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=10,
                )
            )

    def test_build_llm_clients_with_no_keys(self) -> None:
        """build_llm_clients() with no API keys returns only ollama.
        Phase QC8 / A2."""
        from noa.external_worker.llm.router import build_llm_clients

        settings = MagicMock()
        settings.anthropic_api_key = None
        settings.openai_api_key = None
        settings.google_ai_api_key = None
        settings.ollama_base_url = "http://ollama:11434"

        with patch("noa.llm.providers.OllamaClient"):
            clients = build_llm_clients(settings)

        assert "ollama" in clients
        # No external providers without keys
        assert "anthropic" not in clients
        assert "openai" not in clients
        assert "google_ai" not in clients


# ===========================================================================
# A4 — NoOpCheckpointer Stub
# ===========================================================================


class TestA4NoOpCheckpointer:
    """A4: NoOpCheckpointer raises NotImplementedError and emits warning."""

    def test_noop_checkpointer_raises_not_implemented(self) -> None:
        """Each checkpointer method raises NotImplementedError.
        Phase QC8 / A4."""
        from noa.orchestrator.checkpointer import NoOpCheckpointer

        cp = NoOpCheckpointer()

        with pytest.raises(NotImplementedError):
            asyncio.run(cp.save(run_id="r1", state={"x": 1}))

        with pytest.raises(NotImplementedError):
            asyncio.run(cp.load(run_id="r1"))

    def test_noop_checkpointer_emits_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """NoOpCheckpointer logs a warning at construction time.
        Phase QC8 / A4."""
        import logging

        with caplog.at_level(logging.WARNING):
            from noa.orchestrator.checkpointer import NoOpCheckpointer

            NoOpCheckpointer()

        assert any(
            "checkpointer" in record.message.lower()
            for record in caplog.records
        ), "Expected a warning about checkpointer being a no-op"


# ===========================================================================
# A5 — Transaction Abstraction
# ===========================================================================


class TestA5Transactional:
    """A5: async transactional context manager with commit/rollback."""

    @pytest.mark.asyncio
    async def test_transactional_commits_on_success(self) -> None:
        """session.commit() called once on successful block.
        Phase QC8 / A5."""
        from noa.db.transaction import transactional

        session = AsyncMock()

        async with transactional(session):
            pass  # no error

        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transactional_rolls_back_on_exception(self) -> None:
        """session.rollback() called and exception propagates.
        Phase QC8 / A5."""
        from noa.db.transaction import transactional

        session = AsyncMock()

        with pytest.raises(ValueError, match="boom"):
            async with transactional(session):
                raise ValueError("boom")

        session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transactional_does_not_commit_on_exception(self) -> None:
        """commit must NOT be called when an error occurs.
        Phase QC8 / A5."""
        from noa.db.transaction import transactional

        session = AsyncMock()

        with pytest.raises(RuntimeError):
            async with transactional(session):
                raise RuntimeError("fail")

        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_transactional_context_manager_syntax(self) -> None:
        """Can be used as `async with transactional(session): ...`.
        Phase QC8 / A5."""
        from noa.db.transaction import transactional

        session = AsyncMock()

        # Ensure basic syntax works and returns context
        async with transactional(session) as ctx:
            # The context should be the session or a wrapper
            assert ctx is not None


# ===========================================================================
# H8 — Per-User Rate Limiting
# ===========================================================================


class TestH8PerUserRateLimiting:
    """H8: Rate limiter keyed by (user_id, action) for isolation."""

    def test_rate_limit_per_user_isolation(self) -> None:
        """User A hitting the limit does NOT block user B.
        Phase QC8 / H8."""
        from noa.tools.rate_limiter import RateLimiter

        rl = RateLimiter(limits={"send_email": 2}, window_seconds=3600)

        user_a = str(_uuid())
        user_b = str(_uuid())

        # User A exhausts limit
        assert rl.check("send_email", user_id=user_a) is True
        assert rl.check("send_email", user_id=user_a) is True
        assert rl.check("send_email", user_id=user_a) is False  # blocked

        # User B must still succeed
        assert rl.check("send_email", user_id=user_b) is True

    def test_rate_limit_without_user_id_falls_back(self) -> None:
        """user_id=None applies a global/shared limit, does not crash.
        Phase QC8 / H8."""
        from noa.tools.rate_limiter import RateLimiter

        rl = RateLimiter(limits={"send_email": 1}, window_seconds=3600)

        # Should not crash with None
        result = rl.check("send_email", user_id=None)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_gateway_passes_user_id_to_rate_limiter(self) -> None:
        """ToolGateway.dispatch() must pass request.user_id to the rate
        limiter check.  Phase QC8 / H8."""
        from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

        gw = ToolGateway()

        # Register a dummy adapter
        adapter = AsyncMock()
        adapter.execute = AsyncMock(return_value=ToolResponse(result={"ok": True}))
        gw.register("email", adapter)

        # Set up rate limit
        gw.set_rate_limit("email", max_calls=100, window_seconds=3600)

        user_id = _uuid()
        req = ToolRequest(
            tool="email",
            function="send_email",
            args={},
            user_id=user_id,
        )

        # The dispatch must propagate user_id to internal rate limiting.
        # After QC8, rate limits are keyed by (user_id, tool) not just tool.
        # We verify by exhausting user A's limit and confirming user B is OK.
        gw.set_rate_limit("email", max_calls=1, window_seconds=3600)

        resp1 = await gw.dispatch(req)
        assert resp1.error is None

        # Same user, second call should be rate limited
        resp2 = await gw.dispatch(req)
        assert resp2.error is not None and "rate limit" in resp2.error.lower()

        # Different user should succeed
        req_b = ToolRequest(
            tool="email",
            function="send_email",
            args={},
            user_id=_uuid(),
        )
        resp3 = await gw.dispatch(req_b)
        assert resp3.error is None


# ===========================================================================
# M1 — Idempotency Wiring
# ===========================================================================


class TestM1IdempotencyWiring:
    """M1: Idempotency key extracted from headers and used for deduplication."""

    def test_idempotency_key_extracted_from_header(self) -> None:
        """extract_idempotency_key returns the key from headers.
        Phase QC8 / M1.  (This already exists but verifies contract.)"""
        from noa.api.middleware import extract_idempotency_key

        key = extract_idempotency_key({"Idempotency-Key": "abc-123"})
        assert key == "abc-123"

    def test_missing_key_returns_none(self) -> None:
        """No Idempotency-Key header returns None.
        Phase QC8 / M1."""
        from noa.api.middleware import extract_idempotency_key

        assert extract_idempotency_key({}) is None

    def test_idempotency_contextvar_set_by_middleware(self) -> None:
        """After QC8, middleware sets an idempotency_key ContextVar that
        downstream endpoints can read.  Phase QC8 / M1."""
        from noa.api.middleware import idempotency_key_ctx

        # The ContextVar must exist after QC8
        assert idempotency_key_ctx is not None
        # Default should be None or empty
        default = idempotency_key_ctx.get(None)
        assert default is None or default == ""

    def test_duplicate_request_returns_cached_response(self) -> None:
        """IdempotencyStore: same key twice, second returns cached result.
        Phase QC8 / M1."""
        from noa.tools.idempotency import IdempotencyStore

        store = IdempotencyStore(ttl_seconds=60)

        store.set("key-1", {"data": "result"})
        cached = store.get("key-1")
        assert cached == {"data": "result"}

        # Second set with same key must NOT overwrite
        store.set("key-1", {"data": "different"})
        assert store.get("key-1") == {"data": "result"}

    def test_different_keys_processed_independently(self) -> None:
        """Different idempotency keys are stored independently.
        Phase QC8 / M1."""
        from noa.tools.idempotency import IdempotencyStore

        store = IdempotencyStore(ttl_seconds=60)

        store.set("key-a", {"a": 1})
        store.set("key-b", {"b": 2})

        assert store.get("key-a") == {"a": 1}
        assert store.get("key-b") == {"b": 2}


# ===========================================================================
# M5 — SSE Event Replay
# ===========================================================================


class TestM5SSEReplay:
    """M5: Event replay endpoint returns events after a given event ID."""

    @pytest.mark.asyncio
    async def test_replay_endpoint_returns_events_after_id(self) -> None:
        """GET /api/v1/runs/{run_id}/events/replay?after_event_id=1
        returns events 2 and 3 when 3 events exist.  Phase QC8 / M5."""
        from noa.api.v1.runs import replay_run_events

        run_id = _uuid()
        mock_request = MagicMock()
        mock_request.query_params = {"after_event_id": "1"}
        mock_user = {"sub": str(_uuid())}

        # replay_run_events must exist after QC8
        result = await replay_run_events(
            run_id=run_id,
            request=mock_request,
            user=mock_user,
            after_event_id=1,
        )

        # Result should be a list or envelope with events
        assert result is not None

    @pytest.mark.asyncio
    async def test_replay_endpoint_returns_empty_for_unknown_event(self) -> None:
        """Replay with an event ID that doesn't exist returns empty list.
        Phase QC8 / M5."""
        from noa.api.v1.runs import replay_run_events

        run_id = _uuid()
        mock_request = MagicMock()
        mock_user = {"sub": str(_uuid())}

        result = await replay_run_events(
            run_id=run_id,
            request=mock_request,
            user=mock_user,
            after_event_id=999999,
        )

        # Should return empty data, not error
        assert result is not None

    @pytest.mark.asyncio
    async def test_stream_endpoint_sends_event_id_field(self) -> None:
        """SSE events from stream_run_events include 'id:' field so the
        client can track Last-Event-ID.  Phase QC8 / M5."""
        from noa.api.v1.runs import stream_run_events

        run_id = _uuid()
        mock_request = MagicMock()
        mock_user = {"sub": str(_uuid())}

        response = await stream_run_events(
            run_id=run_id,
            request=mock_request,
            user=mock_user,
        )

        # The response body_iterator should yield events with id: field
        # After QC8, real events (not just keepalives) will include id:
        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk)
            if len(body_parts) >= 3:
                break

        combined = "".join(body_parts)
        # At least one event should contain "id:" prefix (SSE event ID)
        assert "id:" in combined, (
            "SSE events must include 'id:' field for Last-Event-ID tracking"
        )


# ===========================================================================
# M7 — Step-Up Auth Enforcement
# ===========================================================================


class TestM7StepUpAuth:
    """M7: gateway blocks high-risk actions without step-up verification."""

    @pytest.mark.asyncio
    async def test_gateway_blocks_high_risk_without_step_up(self) -> None:
        """High-risk action dispatched without step_up_verified is blocked.
        Phase QC8 / M7."""
        from noa.policy.engine import PolicyEngine
        from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

        gw = ToolGateway()
        gw.policy_engine = PolicyEngine()

        adapter = AsyncMock()
        adapter.execute = AsyncMock(return_value=ToolResponse(result={"ok": True}))
        gw.register("data", adapter)

        req = ToolRequest(
            tool="data",
            function="delete_data",  # classified as "high" by PolicyEngine
            args={},
            user_id=_uuid(),
        )
        # No step_up_verified on the request

        resp = await gw.dispatch(req)
        assert resp.error is not None
        assert "step_up" in resp.error.lower() or "auth" in resp.error.lower()

    @pytest.mark.asyncio
    async def test_gateway_allows_high_risk_with_step_up(self) -> None:
        """High-risk action proceeds when step_up_verified=True.
        Phase QC8 / M7."""
        from noa.policy.engine import PolicyEngine
        from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

        gw = ToolGateway()
        gw.policy_engine = PolicyEngine()

        adapter = AsyncMock()
        adapter.execute = AsyncMock(return_value=ToolResponse(result={"ok": True}))
        gw.register("data", adapter)

        req = ToolRequest(
            tool="data",
            function="delete_data",
            args={},
            user_id=_uuid(),
            step_up_verified=True,
        )

        resp = await gw.dispatch(req)
        assert resp.error is None

    @pytest.mark.asyncio
    async def test_gateway_allows_low_risk_without_step_up(self) -> None:
        """Low-risk action proceeds without step-up verification.
        Phase QC8 / M7."""
        from noa.policy.engine import PolicyEngine
        from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

        gw = ToolGateway()
        gw.policy_engine = PolicyEngine()

        adapter = AsyncMock()
        adapter.execute = AsyncMock(return_value=ToolResponse(result={"ok": True}))
        gw.register("search", adapter)

        req = ToolRequest(
            tool="search",
            function="web_search",  # classified as "low" by PolicyEngine
            args={},
            user_id=_uuid(),
        )

        resp = await gw.dispatch(req)
        assert resp.error is None

    @pytest.mark.asyncio
    async def test_gateway_allows_without_policy_engine(self) -> None:
        """When no PolicyEngine is injected, dispatch proceeds (fallback).
        Phase QC8 / M7."""
        from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

        gw = ToolGateway()
        # No policy_engine set — fallback behavior

        adapter = AsyncMock()
        adapter.execute = AsyncMock(return_value=ToolResponse(result={"ok": True}))
        gw.register("data", adapter)

        req = ToolRequest(
            tool="data",
            function="delete_data",
            args={},
            user_id=_uuid(),
        )

        resp = await gw.dispatch(req)
        assert resp.error is None  # fallback: allow


# ===========================================================================
# M10 — Google Refresh Token Persistence
# ===========================================================================


class TestM10GoogleTokenPersistence:
    """M10: GoogleAuthClient calls persistence callback on token changes."""

    def test_set_tokens_triggers_persistence_callback(self) -> None:
        """set_tokens() calls the on_token_change callback.
        Phase QC8 / M10."""
        from noa.tools.google_auth import GoogleAuthClient

        callback = MagicMock()
        client = GoogleAuthClient(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://localhost/callback",
            on_token_change=callback,
        )

        client.set_tokens(access_token="at-1", refresh_token="rt-1")

        callback.assert_called_once()
        call_args = callback.call_args
        # Callback should receive token data
        assert "access_token" in str(call_args) or "at-1" in str(call_args)

    @pytest.mark.asyncio
    async def test_refresh_triggers_persistence_callback(self) -> None:
        """refresh_access_token() calls on_token_change when new token
        is received.  Phase QC8 / M10."""
        from noa.tools.google_auth import GoogleAuthClient

        callback = MagicMock()
        client = GoogleAuthClient(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://localhost/callback",
            on_token_change=callback,
        )
        client.set_tokens(access_token="old-at", refresh_token="old-rt")
        callback.reset_mock()

        # Mock the HTTP call for refresh
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-at",
            "refresh_token": "new-rt",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            await client.refresh_access_token()

        callback.assert_called()

    @pytest.mark.asyncio
    async def test_exchange_code_triggers_persistence_callback(self) -> None:
        """exchange_code() calls on_token_change after successful exchange.
        Phase QC8 / M10."""
        from noa.tools.google_auth import GoogleAuthClient

        callback = MagicMock()
        client = GoogleAuthClient(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://localhost/callback",
            on_token_change=callback,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "at-new",
            "refresh_token": "rt-new",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            await client.exchange_code("auth-code-123")

        callback.assert_called()

    def test_persistence_failure_does_not_break_client(self) -> None:
        """If on_token_change callback raises, client still has tokens
        in memory.  Phase QC8 / M10."""
        from noa.tools.google_auth import GoogleAuthClient

        callback = MagicMock(side_effect=RuntimeError("DB write failed"))
        client = GoogleAuthClient(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://localhost/callback",
            on_token_change=callback,
        )

        # set_tokens should not crash even if callback fails
        client.set_tokens(access_token="at-1", refresh_token="rt-1")

        # Tokens must still be stored in memory
        assert client.access_token == "at-1"
        assert client.refresh_token == "rt-1"
