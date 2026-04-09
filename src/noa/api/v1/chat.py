"""Chat endpoint — web client chat submission with SSE streaming."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from noa.api.middleware import idempotency_key_ctx, trace_id_ctx
from noa.auth.middleware import AuthUser, require_auth
from noa.db.rls import set_domain_context
from noa.orchestrator.runner import OrchestratorRunner
from noa.queue.health import HealthChecker
from noa.types import PrivacyMode, RiskTier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# UX-H1: SSE keepalive interval — send comment pings to prevent proxy timeouts
# during long-running tool calls (e.g. Calendar API calls can take >30s).
_SSE_KEEPALIVE_INTERVAL = 15  # seconds

# DI2 (RV-M1): Chat-level idempotency key prefix in the DB table.
# Tool-level keys are stored without a prefix; chat-level keys use "chat:"
# to avoid collision.
_CHAT_IDEM_PREFIX = "chat:"


async def _check_chat_idempotency(idem_key: str) -> bool:
    """Return True if this chat idempotency key has already been processed.

    DI2: Replaces the in-memory dict with a DB-backed check using the
    ``idempotency_keys`` table.  Falls back to False (allow) on any DB error
    so a database hiccup never blocks the user.
    """
    factory = _get_session_factory()
    if factory is None:
        return False
    try:
        from sqlalchemy import select

        from noa.db.models.idempotency_key import IdempotencyKey

        full_key = f"{_CHAT_IDEM_PREFIX}{idem_key}"
        async with factory() as session:
            stmt = select(IdempotencyKey.id).where(IdempotencyKey.key == full_key)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None
    except Exception:  # noqa: BLE001
        logger.warning(
            "Chat idempotency DB check failed for key=%s", idem_key, exc_info=True
        )
        return False


async def _register_chat_idempotency(idem_key: str) -> None:
    """Store a chat idempotency key in the DB (best-effort, no-op on error).

    DI2: Replaces the in-memory dict registration.  Uses ON CONFLICT DO NOTHING
    so concurrent requests with the same key are handled gracefully.
    """
    factory = _get_session_factory()
    if factory is None:
        return
    try:
        from noa.db.models.idempotency_key import IdempotencyKey

        full_key = f"{_CHAT_IDEM_PREFIX}{idem_key}"
        async with factory() as session:
            # Try a simple insert; if the key already exists (race), ignore.
            try:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(IdempotencyKey).values(
                    key=full_key,
                    response_json="{}",  # placeholder — chat idem keys carry no payload
                ).on_conflict_do_nothing(index_elements=["key"])
                await session.execute(stmt)
                await session.commit()
            except Exception:  # noqa: BLE001
                # Non-Postgres (SQLite in tests): fall back to a plain INSERT
                try:
                    from sqlalchemy import insert as sa_insert

                    stmt_plain = sa_insert(IdempotencyKey).values(
                        key=full_key,
                        response_json="{}",
                    )
                    await session.execute(stmt_plain)
                    await session.commit()
                except Exception as _inner_exc:  # noqa: BLE001
                    logger.debug(
                        "Chat idempotency fallback insert skipped: %s", _inner_exc
                    )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Chat idempotency DB register failed for key=%s", idem_key, exc_info=True
        )


class ChatRequest(BaseModel):
    """Request body for chat submission."""

    message: str
    thread_id: str | None = None
    privacy_mode: Literal["private", "external"] | None = None
    model: str | None = None
    provider: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    system_prompt: str | None = None
    tool_scope: str | None = None


def get_runner() -> OrchestratorRunner | None:
    """Get the OrchestratorRunner from app state."""
    from noa.api.app_state import get_runner

    return get_runner()


def _get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    """Get the DB session factory from app state."""
    from noa.api.app_state import get_session_factory

    return get_session_factory()


# Backward-compatible alias for pre-QC3 callers and tests
get_session_factory = _get_session_factory


def get_health_checker() -> HealthChecker | None:
    """Get the HealthChecker from app state."""
    from noa.api.app_state import get_health_checker as _ghc

    return _ghc()


async def _find_active_run(thread_id: str, user_id: str) -> str | None:
    """Find an active (non-terminal) run for the given thread.

    Returns the run_id as a string if an active run exists, else None.
    A Run represents the full task lifecycle — follow-up messages in the
    same thread continue the same run rather than creating new ones.
    """
    factory = _get_session_factory()
    if factory is None:
        return None

    try:
        from sqlalchemy import select

        from noa.db.models.run import Run

        tid = uuid.UUID(thread_id)
        uid = uuid.UUID(user_id)

        async with factory() as session:
            result = await session.execute(
                select(Run.id)
                .where(
                    Run.thread_id == tid,
                    Run.user_id == uid,
                    Run.status.in_(["pending", "running", "awaiting_approval"]),
                )
                .order_by(Run.created_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return str(row) if row else None
    except Exception:  # noqa: BLE001
        logger.debug("Failed to find active run for thread %s", thread_id)
        return None


@router.post("/chat", response_model=None)
async def submit_chat(
    body: ChatRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> StreamingResponse | JSONResponse:
    """Submit a chat message and stream SSE events back.

    Creates a Run and Conversation, invokes the OrchestratorRunner,
    and streams events as SSE frames.
    """
    rid = trace_id_ctx.get("")
    user_id = str(user.user_id)

    # MVP-H3: Check private domain availability before classifying privacy_mode
    _checker = get_health_checker()
    private_available: bool = _checker.is_available() if _checker is not None else True

    # Determine effective privacy_mode.
    # Priority:
    # 1. Explicit "private" from client → always private.
    # 2. Existing thread → inherit its domain (avoids BE-C3 domain mismatch).
    # 3. New thread → content-classify the message so that private content
    #    (journal, diary, etc.) is queued when the private worker is unavailable.
    #    The frontend default of "external" must not suppress this detection.
    # Cache _get_thread_domain result to avoid a second DB round-trip at the
    # OI8 domain-redirect check below (Fix: suggested-4).
    _cached_thread_domain: str | None = None
    if body.privacy_mode == "private":
        privacy_mode: str = PrivacyMode.PRIVATE
    elif body.thread_id is not None:
        _cached_thread_domain = await _get_thread_domain(body.thread_id, user_id)
        privacy_mode = (
            _cached_thread_domain or body.privacy_mode or PrivacyMode.EXTERNAL
        )
    elif body.privacy_mode is None:
        # No explicit mode and no thread — classify the message content.
        # Only runs when the client hasn't expressed a preference; an explicit
        # "external" from the client is respected as-is (Transparency Principle).
        from noa.privacy.classifier import PrivacyClassifier
        _user_settings_for_clf = await _load_user_settings(user.user_id)
        _custom_keywords = _user_settings_for_clf.get("private_keywords") or []
        _clf = PrivacyClassifier(custom_keywords=_custom_keywords)
        _clf_result = _clf.classify(
            {"messages": [{"role": "user", "content": body.message}]},
            private_available=private_available,
        )
        privacy_mode = _clf_result.domain
    else:
        privacy_mode = body.privacy_mode

    # BE-M4: Structured log context for queryable logs
    log_ctx = {
        "trace_id": rid,
        "user_id": user_id,
    }
    logger.info(
        "Chat request received: user_id=%s trace_id=%s privacy_mode=%s",
        user_id,
        rid,
        privacy_mode,
        extra=log_ctx,
    )

    # DI2 (RV-M1): Check idempotency key for duplicate request detection
    # Uses DB-backed check (replaces in-memory dict from M1).
    idem_key = idempotency_key_ctx.get()
    if idem_key and await _check_chat_idempotency(idem_key):
        return JSONResponse(
            status_code=409,
            content={"ok": False, "error": {"code": "DUPLICATE_REQUEST",
                     "message": "Duplicate request (same Idempotency-Key)"}},
        )

    thread_id = body.thread_id or str(uuid.uuid4())

    # Reuse active run on this thread instead of creating a new one per message.
    # A Run = full task lifecycle; follow-up messages are steps in the same run.
    existing_run_id = (
        await _find_active_run(thread_id, user_id)
        if body.thread_id
        else None
    )
    run_id = existing_run_id or str(uuid.uuid4())
    is_new_run = existing_run_id is None

    # DI2 (RV-M1): Register idempotency key in DB (best-effort, non-blocking)
    if idem_key:
        await _register_chat_idempotency(idem_key)

    runner = get_runner()

    # W22-H1/H2: Load user settings for agent limits and approvals toggle
    user_settings = await _load_user_settings(user.user_id)

    # MVP-H3: If private domain is requested but unavailable, enqueue the task
    if privacy_mode == PrivacyMode.PRIVATE and not private_available:
        # MVP-M2: Create Run + Conversation rows so queued request appears on Runs page.
        # Use initial_status="queued" directly — avoids a state machine transition.
        await _make_run_service(
            user_id, thread_id, run_id, privacy_mode, body.message,
            initial_status="queued",
            create_run=is_new_run,
        )
        queue_id = await _enqueue_private_chat(
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            body=body,
            timeout_seconds=user_settings.get("timeout_seconds", 120),
        )
        return StreamingResponse(
            _queued_event_stream(run_id=run_id, thread_id=thread_id, queue_id=queue_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Trace-ID": rid,
            },
        )

    # OI8: Smart domain redirect — instead of returning a 403 DOMAIN_MISMATCH
    # error, auto-create a new thread in the correct domain and route the
    # message there.  The meta event signals the frontend so it can switch
    # context and show a toast notification.
    redirected = False
    original_thread_id: str | None = None
    if body.thread_id is not None:
        # Reuse cached result from the privacy_mode determination above to
        # avoid a second DB round-trip (OI8 suggested-4).
        thread_domain = (
            _cached_thread_domain
            if _cached_thread_domain is not None
            else await _get_thread_domain(body.thread_id, user_id)
        )
        if thread_domain is not None and thread_domain != privacy_mode:
            # Mismatch confirmed — create a fresh thread in the requested domain.
            original_thread_id = thread_id
            thread_id = str(uuid.uuid4())
            run_id = str(uuid.uuid4())
            is_new_run = True
            redirected = True
            logger.info(
                "OI8 domain redirect: thread %s (%s) → new thread %s (%s)",
                original_thread_id,
                thread_domain,
                thread_id,
                privacy_mode,
            )

    async def event_stream() -> Any:
        """Generate SSE events from the runner."""
        # Initial metadata event with run_id and thread_id
        meta: dict[str, Any] = {
            "event_type": "meta",
            "run_id": run_id,
            "thread_id": thread_id,
        }
        if redirected:
            meta["redirected"] = True
            meta["original_thread_id"] = original_thread_id
            meta["redirect_reason"] = "domain_mismatch"
        yield f"data: {json.dumps(meta)}\n\n"

        if runner is None:
            # No runner configured — return error
            err = {
                "event_type": "error",
                "payload": {"error": "Chat pipeline not configured"},
            }
            yield f"data: {json.dumps(err)}\n\n"
            return

        # Create Conversation + Run rows in DB (skip if reusing an existing run)
        run_svc = await _make_run_service(
            user_id, thread_id, run_id, privacy_mode, body.message,
            create_run=is_new_run,
        )

        # Load conversation history for multi-turn context
        history = await _load_thread_history(thread_id, user_id)

        llm_usage: list[dict[str, Any]] = []
        response_text = ""
        collected_events: list[dict[str, Any]] = []
        has_pending_approval = False

        # UX-H1: Wrap the runner async generator so we can interleave keepalive
        # pings without blocking. We race each event against a 15s sleep; if the
        # sleep wins we emit an SSE comment (": keepalive") which proxies and
        # browsers accept without triggering the error handler.
        async def _run_with_keepalive() -> Any:
            event_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

            async def _producer() -> None:
                try:
                    async for event in runner.run(
                        message=body.message,
                        run_service=run_svc,
                        run_id=run_id,
                        privacy_mode=privacy_mode,
                        model=body.model,
                        provider=body.provider,
                        system_prompt=body.system_prompt,
                        temperature=body.temperature,
                        max_tokens=body.max_tokens,
                        user_id=user_id,
                        trace_id=rid,
                        history=history,
                        max_tool_calls=user_settings.get("max_tool_calls", 10),
                        max_retries=user_settings.get("max_retries", 3),
                        timeout_seconds=user_settings.get("timeout_seconds", 120),
                        approvals_enabled=user_settings.get("approvals_enabled", True),
                        private_available=private_available,
                        tool_scope=body.tool_scope,
                        node_models=user_settings.get("node_models", {}),
                        eval_config=user_settings.get("eval_config") or {},
                    ):
                        await event_queue.put(event)
                finally:
                    # Sentinel to signal completion
                    await event_queue.put(None)

            producer_task = asyncio.create_task(_producer())
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(
                            event_queue.get(),
                            timeout=_SSE_KEEPALIVE_INTERVAL,
                        )
                        if event is None:
                            # Producer finished
                            break
                        yield event
                    except TimeoutError:
                        # Yield a sentinel dict that the caller treats as keepalive
                        yield {"_keepalive": True}
            finally:
                producer_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):  # noqa: BLE001
                    await producer_task

        try:
            async for event in _run_with_keepalive():
                if event.get("_keepalive"):
                    # SSE comment — keeps the connection alive, ignored by JS
                    yield ": keepalive\n\n"
                    continue

                # Collect events for bulk persistence after stream ends
                collected_events.append(event)

                # Capture response and llm_usage from result_ready for persistence
                if event.get("event_type") == "result_ready":
                    payload = event.get("payload", {})
                    llm_usage = payload.get("llm_usage", [])
                    response_text = payload.get("response", "")

                # Persist approval requests to DB so Approvals page shows them
                if event.get("event_type") == "approval_requested":
                    approval_id = await _create_approval(
                        user_id, run_id, event.get("payload", {}), privacy_mode,
                    )
                    # Inject approval_id into the SSE event payload
                    if approval_id:
                        event.setdefault("payload", {})["approval_id"] = approval_id
                    has_pending_approval = True

                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.error("Chat stream error: %s", str(exc), extra=log_ctx)
            err_event = {
                "event_type": "error",
                "payload": {"error": "An error occurred processing your request."},
            }
            collected_events.append(err_event)
            yield f"data: {json.dumps(err_event)}\n\n"

        # ST2: Extract tool-aware turn messages from collected SSE events so
        # tool_calls and tool results are persisted for multi-turn context.
        turn_messages = _extract_turn_messages(collected_events)

        # Persist messages, usage, events, and run status to DB (best-effort)
        await _persist_messages(
            user_id, thread_id, run_id, body.message, response_text, privacy_mode,
            turn_messages=turn_messages,
        )
        if llm_usage:
            await _record_usage(user_id, run_id, llm_usage)
        await _persist_run_events(run_id, collected_events)
        # Run lifecycle: mark completed unless an error or approval is pending.
        if has_pending_approval:
            final_status = "awaiting_approval"
        elif not response_text:
            final_status = "failed"
        else:
            final_status = "completed"
        await _update_run_status(
            run_id, final_status,
            summary=_build_run_summary(collected_events, response_text),
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Trace-ID": rid,
        },
    )


async def _load_user_settings(user_id: Any) -> dict[str, Any]:
    """Load user settings for agent limits and governance toggles (best-effort).

    Returns a dict with agent limit fields. Falls back to safe defaults
    if DB is unavailable so the chat pipeline always has valid values.
    W22-H1, W22-H2: Provides max_tool_calls, max_retries, timeout_seconds,
    approvals_enabled to the orchestrator runner.
    MC1: Also provides node_models for per-node model configuration.
    PC1: Also provides private_keywords for the privacy classifier.
    """
    defaults: dict[str, Any] = {
        "max_tool_calls": 10,
        "max_retries": 3,
        "timeout_seconds": 120,
        "approvals_enabled": True,
        "node_models": {},
        "private_keywords": [],
        "eval_config": {},
    }
    factory = _get_session_factory()
    if factory is None:
        return defaults

    try:
        from noa.settings.repository import SettingsRepository
        from noa.settings.service import SettingsService

        async with factory() as session:
            service = SettingsService(SettingsRepository(session))
            data = await service.get_settings(user_id)
            return {
                "max_tool_calls": (
                    data.get("max_tool_calls") or defaults["max_tool_calls"]
                ),
                "max_retries": (
                    data.get("max_retries") or defaults["max_retries"]
                ),
                "timeout_seconds": (
                    data.get("timeout_seconds") or defaults["timeout_seconds"]
                ),
                "approvals_enabled": data.get("approvals_enabled", True),
                # MC1: Per-node model overrides (empty dict = use defaults)
                "node_models": data.get("node_models") or {},
                # PC1: Custom private keywords (empty list = use built-in defaults)
                "private_keywords": data.get("private_keywords") or [],
                # OV4 / UX-EV1: Evaluator config (empty dict = use hardcoded defaults)
                "eval_config": data.get("eval_config") or {},
            }
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load user settings for agent limits")
        return defaults



async def _get_thread_domain(thread_id: str, user_id: str) -> str | None:
    """Return the domain of an existing thread, or None if not found."""
    factory = _get_session_factory()
    if factory is None:
        return None
    try:
        from sqlalchemy import select

        from noa.db.models.conversation import Conversation

        tid = uuid.UUID(thread_id)
        uid = uuid.UUID(user_id)
        async with factory() as session:
            result = await session.execute(
                select(Conversation.domain).where(
                    Conversation.id == tid,
                    Conversation.user_id == uid,
                )
            )
            row = result.scalar_one_or_none()
            return str(row) if row is not None else None
    except Exception:  # noqa: BLE001
        return None


async def _make_run_service(
    user_id: str,
    thread_id: str,
    run_id: str,
    privacy_mode: str,
    user_message: str,
    *,
    initial_status: str = "running",
    create_run: bool = True,
) -> Any:
    """Create Conversation + Run rows in DB, return a no-op service for the runner.

    The runner calls sync methods (update_status, append_event) which
    can't work with AsyncSession.  We create the rows here with
    proper async operations and let the runner use a no-op service.
    Run status updates happen after stream completion.

    MVP-M2: Accepts optional initial_status to support "queued" runs that are
    created before the private domain is available.

    When ``create_run=False`` (reusing an existing run), only the Conversation
    row is ensured and the existing run is transitioned back to "running" if
    it was in an interruptible state (e.g. awaiting_approval).
    """
    factory = _get_session_factory()
    if factory is not None:
        try:
            from sqlalchemy import select

            from noa.db.models.conversation import Conversation
            from noa.db.models.run import Run

            tid = uuid.UUID(thread_id)
            uid = uuid.UUID(user_id)

            async with factory() as session:
                # RLS1: set domain context so Postgres RLS policies apply
                await set_domain_context(session, privacy_mode)
                # Ensure conversation exists (FK for runs.thread_id)
                result = await session.execute(
                    select(Conversation).where(Conversation.id == tid)
                )
                existing = result.scalar_one_or_none()
                if existing is None:
                    title = user_message[:50].strip() or "New thread"
                    session.add(Conversation(
                        id=tid, user_id=uid, title=title, domain=privacy_mode,
                    ))

                if create_run:
                    session.add(Run(
                        id=uuid.UUID(run_id),
                        user_id=uid,
                        thread_id=tid,
                        status=initial_status,
                        risk_tier=RiskTier.LOW,
                        privacy_mode=privacy_mode,
                    ))
                else:
                    # Reusing existing run — ensure it's back in "running"
                    run_result = await session.execute(
                        select(Run).where(Run.id == uuid.UUID(run_id))
                    )
                    run = run_result.scalar_one_or_none()
                    if run is not None and run.status != "running":
                        run.status = "running"
                        run.updated_at = datetime.now(UTC)

                await session.commit()
        except Exception:  # noqa: BLE001
            logger.debug("create_run failed", exc_info=True)

    return _NoOpRunService()


class _NoOpRunService:
    """No-op RunService for when DB is not available."""

    async def create_run(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def update_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def append_event(self, *args: Any, **kwargs: Any) -> None:
        pass


async def _load_thread_history(
    thread_id: str,
    user_id: str,
) -> list[dict[str, Any]]:
    """Load prior messages from the thread for conversation context.

    Returns a list of {role, content} dicts ordered by timestamp.
    Limited to the most recent 20 messages to avoid token overflow.
    """
    factory = _get_session_factory()
    if factory is None:
        return []

    try:
        from sqlalchemy import select

        from noa.db.models.conversation import Message

        tid = uuid.UUID(thread_id)
        uid = uuid.UUID(user_id)

        async with factory() as session:
            result = await session.execute(
                select(Message)
                .where(Message.thread_id == tid, Message.user_id == uid)
                .order_by(Message.timestamp.desc())
                .limit(20)
            )
            rows = result.scalars().all()
            # Reverse to chronological order; reconstruct full message dicts
            # including tool_calls and tool-role messages for ST2 (CHAT-H1).
            msgs: list[dict[str, Any]] = []
            for m in reversed(rows):
                if m.role == "tool":
                    msgs.append({
                        "role": "tool",
                        "tool_call_id": m.tool_call_id or "",
                        "name": m.tool_name or "",
                        "content": m.content or "",
                    })
                elif m.role == "assistant":
                    msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": m.content or "",
                    }
                    if m.tool_calls:
                        msg["tool_calls"] = m.tool_calls
                    msgs.append(msg)
                elif m.role == "user" and m.content:
                    msgs.append({"role": "user", "content": m.content})
            return msgs
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load thread history for %s", thread_id)
        return []


def _extract_turn_messages(
    collected_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reconstruct tool-aware turn messages from SSE events.

    ST2 (CHAT-H1): Builds a list of message dicts for persistence by extracting
    tool_call data from ``tool_called`` events and tool results from
    ``tool_result``/``tool_end`` events.

    DI1 (W26-M1): Correctly handles multiple tool-call *rounds* within one
    agent turn (tool A → result A → tool B → result B ...).  Each round is
    emitted as a separate assistant+tool message pair, which is what LLM APIs
    require for valid multi-turn tool history.

    Also handles providers (Ollama, Kimi) that omit ``id`` on tool calls by
    generating synthetic IDs of the form ``tool_<index>`` so that result
    matching never collides across different tool calls.

    Returns a list that may include:
    - ``{"role": "assistant", "content": None, "tool_calls": [...]}`` — when
      the assistant made tool calls during this round
    - ``{"role": "tool", "tool_call_id": "...", "name": "...", "content": "..."}``
      — one entry per tool result in the same round
    """
    import json as _json_mod

    # -----------------------------------------------------------------------
    # Pass 1: Group SSE events into ordered rounds.
    # A round boundary is detected when a tool_called event arrives AFTER
    # at least one result has already been seen in the current round.
    # -----------------------------------------------------------------------
    # Each round is a list of raw events belonging to that round.
    rounds: list[list[dict[str, Any]]] = []
    current_round: list[dict[str, Any]] = []
    current_round_has_result = False
    # Running counter for synthetic ID generation (global across rounds so
    # IDs are unique within the entire turn, not just within a round).
    _synthetic_id_counter = 0

    for event in collected_events:
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})

        if event_type == "tool_called":
            tc = payload.get("tool_call", {})
            if not (tc and isinstance(tc, dict)):
                continue
            # DI1: Generate synthetic ID for providers that omit it
            if not tc.get("id"):
                tc = dict(tc)  # copy to avoid mutating the original event
                tc["id"] = f"tool_{_synthetic_id_counter}"
                _synthetic_id_counter += 1

            if current_round_has_result:
                # The previous round is complete — save it and start a new one.
                rounds.append(current_round)
                current_round = []
                current_round_has_result = False

            current_round.append({"_type": "call", "tc": tc})

        elif event_type in ("tool_result", "tool_end"):
            tr = payload.get("tool_result") or payload.get("result") or {}
            if not isinstance(tr, dict):
                continue
            tool_name = payload.get("tool_name") or tr.get("name", "")
            content = tr.get("error") or _json_mod.dumps(
                {k: v for k, v in tr.items() if k != "name"},
                default=str,
            )
            current_round.append(
                {"_type": "result", "tool_name": tool_name, "content": content}
            )
            current_round_has_result = True

    # Flush the last round
    if current_round:
        rounds.append(current_round)

    if not rounds:
        return []

    # -----------------------------------------------------------------------
    # Pass 2: Convert each round into (assistant_msg, tool_msg...) pairs.
    # -----------------------------------------------------------------------
    turn_msgs: list[dict[str, Any]] = []

    for round_events in rounds:
        calls = [e for e in round_events if e["_type"] == "call"]
        results = [e for e in round_events if e["_type"] == "result"]

        if not calls and not results:
            continue

        # Build the assistant message for this round (may have no calls if
        # we somehow got orphan results — rare, but handle gracefully).
        if calls:
            tool_calls_payload = [e["tc"] for e in calls]
            turn_msgs.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls_payload,
            })

        # Map tool name → list of call IDs so we can match results in order
        # (handles the same tool being called multiple times in one round).
        name_to_call_ids: dict[str, list[str]] = {}
        for e in calls:
            tc = e["tc"]
            name = tc.get("name", "")
            name_to_call_ids.setdefault(name, []).append(tc.get("id", ""))

        # Track which call IDs have been consumed so we don't double-match
        consumed_call_ids: set[str] = set()

        for res_event in results:
            tool_name = res_event["tool_name"]
            content = res_event["content"]

            # Find the first unconsumed call ID for this tool name
            call_id = ""
            candidates = name_to_call_ids.get(tool_name, [])
            for cid in candidates:
                if cid not in consumed_call_ids:
                    call_id = cid
                    consumed_call_ids.add(cid)
                    break

            turn_msgs.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": tool_name,
                "content": content,
            })

    return turn_msgs


async def _persist_messages(
    user_id: str,
    thread_id: str,
    run_id: str,
    user_message: str,
    assistant_response: str,
    privacy_mode: str = "external",
    turn_messages: list[dict[str, Any]] | None = None,
) -> None:
    """Persist user + assistant messages to the messages table.

    Creates the Conversation row if it doesn't exist yet (new thread from chat).
    BE-C3: New conversations are created with the correct domain.
    ST2: Also persists tool_calls on assistant messages and tool-role messages
    so multi-turn conversations retain full tool context (CHAT-H1).

    Args:
        turn_messages: Optional list of message dicts from this turn, ordered
            as [assistant_with_tool_calls, tool_result, ...]. When provided,
            these are persisted in addition to the user/assistant text messages.
    """
    factory = _get_session_factory()
    if factory is None:
        return

    try:
        from sqlalchemy import select

        from noa.db.models.conversation import Conversation, Message
        from noa.db.transaction import transactional

        tid = uuid.UUID(thread_id)
        uid = uuid.UUID(user_id)

        async with factory() as session, transactional(session):
            # Ensure conversation exists
            result = await session.execute(
                select(Conversation).where(Conversation.id == tid)
            )
            conv = result.scalar_one_or_none()
            if conv is None:
                # Derive title from first ~50 chars of user message
                title = user_message[:50].strip() or "New thread"
                session.add(
                    Conversation(id=tid, user_id=uid, title=title, domain=privacy_mode)
                )
            elif conv.title in ("New Thread", "New thread", ""):
                # Update placeholder title with first real message
                conv.title = user_message[:50].strip() or conv.title

            # User message
            session.add(Message(
                id=uuid.uuid4(),
                thread_id=tid,
                user_id=uid,
                role="user",
                content=user_message,
                run_id=run_id,
            ))

            # ST2: Persist tool-aware turn messages (assistant with tool_calls
            # and tool-role messages) before the final assistant text response.
            if turn_messages:
                for tm in turn_messages:
                    role = tm.get("role", "")
                    if role == "assistant":
                        tcs = tm.get("tool_calls") or None
                        # Only persist if there are tool_calls (intermediate
                        # assistant turns); the final text response is persisted
                        # separately below.
                        if tcs:
                            session.add(Message(
                                id=uuid.uuid4(),
                                thread_id=tid,
                                user_id=uid,
                                role="assistant",
                                content=tm.get("content") or None,
                                tool_calls=tcs,
                                run_id=run_id,
                            ))
                    elif role == "tool":
                        session.add(Message(
                            id=uuid.uuid4(),
                            thread_id=tid,
                            user_id=uid,
                            role="tool",
                            content=tm.get("content") or None,
                            tool_call_id=tm.get("tool_call_id") or None,
                            tool_name=tm.get("name") or None,
                            run_id=run_id,
                        ))

            # Assistant message (if we got a response)
            if assistant_response:
                session.add(Message(
                    id=uuid.uuid4(),
                    thread_id=tid,
                    user_id=uid,
                    role="assistant",
                    content=assistant_response,
                    run_id=run_id,
                ))
    except Exception:  # noqa: BLE001
        logger.warning("Failed to persist messages for run %s", run_id, exc_info=True)


def _build_run_summary(
    collected_events: list[dict[str, Any]],
    response_text: str,
) -> str | None:
    """Derive a meaningful run summary from collected SSE events.

    Priority:
    1. Tool result errors  -> "Failed: <error>"
    2. Pending approvals   -> "Awaiting approval for <tool>"
    3. Successful tools    -> "<tool1>, <tool2> completed"
    4. Fallback            -> first 200 chars of response_text
    """
    tool_errors: list[str] = []
    approval_tool: str | None = None
    successful_tools: list[str] = []

    for event in collected_events:
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})

        if event_type == "tool_result":
            tool_name = payload.get("tool", "") or payload.get("tool_name", "")
            error = payload.get("error") or (
                payload.get("result", {}).get("error")
                if isinstance(payload.get("result"), dict)
                else None
            )
            if error:
                label = f"{tool_name}: {error}" if tool_name else str(error)
                tool_errors.append(label[:120])
            elif tool_name:
                successful_tools.append(tool_name)

        elif event_type == "approval_requested":
            tool_name = payload.get("tool", "") or payload.get("function", "")
            if tool_name and approval_tool is None:
                approval_tool = tool_name

    if tool_errors:
        return ("Failed: " + "; ".join(tool_errors))[:200]

    if approval_tool:
        return f"Awaiting approval for {approval_tool}"[:200]

    if successful_tools:
        unique = list(dict.fromkeys(successful_tools))  # preserve order, dedupe
        return (", ".join(unique) + " completed")[:200]

    if response_text:
        return response_text[:200].strip()

    return None


async def _update_run_status(
    run_id: str, status: str, *, summary: str | None = None,
) -> None:
    """Update run status via RunService (best-effort).

    BE-H5: Routes through RunService to enforce state machine transitions
    and trigger push notifications, rather than doing a raw UPDATE.
    """
    factory = _get_session_factory()
    if factory is None:
        return

    try:
        from sqlalchemy import select

        from noa.db.models.run import Run
        from noa.db.transaction import transactional
        from noa.runs.service import RunService

        async with factory() as session, transactional(session):
            rid = uuid.UUID(run_id)
            result = await session.execute(
                select(Run).where(Run.id == rid)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return

            # Only transition if status actually changes
            if run.status != status:
                svc = RunService(session=session)
                await svc.update_status(rid, status)

            # Always update summary with latest activity
            if summary:
                run.summary = summary
                run.updated_at = datetime.now(UTC)
    except ValueError:
        # Invalid transition (run may already be in terminal state) — ignore
        logger.debug(
            "Skipping invalid run status transition for %s -> %s", run_id, status
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to update run status for %s", run_id)


async def _record_usage(
    user_id: str,
    run_id: str,
    llm_usage: list[dict[str, Any]],
) -> None:
    """Persist LLM usage records to UsageStats (best-effort)."""
    factory = _get_session_factory()
    if factory is None:
        return

    try:
        from noa.db.models.usage import UsageStats
        from noa.db.transaction import transactional

        async with factory() as session, transactional(session):
            for entry in llm_usage:
                row = UsageStats(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID(user_id),
                    provider=entry.get("provider", ""),
                    model_name=entry.get("model", ""),
                    input_tokens=entry.get("input_tokens", 0),
                    output_tokens=entry.get("output_tokens", 0),
                    cost_usd=Decimal(str(entry.get("cost_usd", 0))),
                    run_id=uuid.UUID(run_id),
                )
                session.add(row)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to persist usage stats for run %s", run_id)


async def _persist_run_events(
    run_id: str,
    events: list[dict[str, Any]],
) -> None:
    """Bulk-persist collected run events to the run_events table (best-effort)."""
    factory = _get_session_factory()
    if factory is None or not events:
        return

    try:
        from noa.db.models.run import RunEvent
        from noa.db.transaction import transactional
        from noa.runs.schemas import VALID_EVENT_TYPES

        async with factory() as session, transactional(session):
            for evt in events:
                event_type = evt.get("event_type", "")
                if event_type not in VALID_EVENT_TYPES:
                    continue
                payload = evt.get("payload", {})
                ts_str = evt.get("timestamp")
                ts = (
                    datetime.fromisoformat(ts_str)
                    if ts_str
                    else datetime.now(UTC)
                )
                session.add(RunEvent(
                    id=uuid.uuid4(),
                    run_id=uuid.UUID(run_id),
                    event_type=event_type,
                    timestamp=ts,
                    payload=payload,
                ))
    except Exception:  # noqa: BLE001
        logger.warning("Failed to persist run events for run %s", run_id, exc_info=True)


async def _create_approval(
    user_id: str,
    run_id: str,
    payload: dict[str, Any],
    privacy_mode: str = "external",
) -> str | None:
    """Create a pending Approval row in the DB (best-effort).

    Returns the approval_id string, or None on failure.
    """
    factory = _get_session_factory()
    if factory is None:
        return "no-db-factory"  # fail-closed: signal rather than silent None

    try:
        from noa.db.models.approval import Approval
        from noa.db.transaction import transactional

        tool = payload.get("tool", "")
        function = payload.get("function", "")
        args = payload.get("args", {})
        risk_tier = payload.get("risk_tier", "medium")

        # Build preview text with tool info
        preview = f"{tool}.{function}"
        if args:
            preview += f"\n{json.dumps(args, indent=2, default=str)}"

        approval_id = uuid.uuid4()
        async with factory() as session, transactional(session):
            session.add(Approval(
                id=approval_id,
                run_id=uuid.UUID(run_id),
                user_id=uuid.UUID(user_id),
                risk_tier=risk_tier,
                tool_name=tool or None,
                function_name=function or None,
                preview_text=preview,
                decision="pending",
                domain=privacy_mode,
            ))
        logger.info("Created approval %s for run %s", approval_id, run_id)
        return str(approval_id)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to create approval for run %s", run_id, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# MVP-H3: Queue helpers — private domain unavailable path
# ---------------------------------------------------------------------------


async def _enqueue_private_chat(
    *,
    run_id: str,
    thread_id: str,
    user_id: str,
    body: ChatRequest,
    timeout_seconds: int = 120,
) -> str | None:
    """Enqueue a private chat task when the private domain is unavailable.

    Returns the queue_id string on success, or None if enqueueing failed.
    """
    factory = _get_session_factory()
    if factory is None:
        logger.warning("Cannot enqueue: no session factory configured")
        return None

    try:
        from noa.queue.durable import DurableQueue

        async with factory() as session:
            queue = DurableQueue(session)
            queue_id = await queue.enqueue(
                task_type="private.chat",
                payload={
                    "user_id": user_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "message": body.message,
                    "model": body.model,
                    "provider": body.provider,
                    "timeout_seconds": timeout_seconds,
                },
                idempotency_key=uuid.UUID(run_id),
            )
            await session.commit()
            logger.info("Enqueued private.chat task %s for run %s", queue_id, run_id)
            return str(queue_id)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to enqueue private.chat task for run %s", run_id)
        return None


async def _queued_event_stream(
    *,
    run_id: str,
    thread_id: str,
    queue_id: str | None,
) -> Any:
    """Yield a minimal SSE stream telling the client the task was queued.

    MVP-L2: Emits a meta event first so clients can track run_id/thread_id,
    matching the contract of the normal streaming path.
    """
    # MVP-L2: meta event first — clients rely on this for run_id/thread_id tracking
    meta_event = {
        "event_type": "meta",
        "run_id": run_id,
        "thread_id": thread_id,
    }
    yield f"data: {json.dumps(meta_event)}\n\n"

    queued_event = {
        "event_type": "queued",
        "payload": {
            "queue_id": queue_id,
            "message": (
                "Private domain is currently unavailable. Your request has been"
                " queued and will be processed when the private worker comes"
                " back online."
            ),
        },
    }
    yield f"data: {json.dumps(queued_event)}\n\n"

    done_event = {
        "event_type": "done",
        "payload": {"run_id": run_id},
    }
    yield f"data: {json.dumps(done_event)}\n\n"
