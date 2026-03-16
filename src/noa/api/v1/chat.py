"""Chat endpoint — web client chat submission with SSE streaming."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from noa.api.middleware import idempotency_key_ctx, trace_id_ctx
from noa.auth.middleware import AuthUser, require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# M1: In-memory idempotency key tracking (TTL-based cleanup)
_active_idempotency_keys: dict[str, float] = {}
_IDEMPOTENCY_TTL_SECONDS = 300  # 5 minutes

# UX-H1: SSE keepalive interval — send comment pings to prevent proxy timeouts
# during long-running tool calls (e.g. Calendar API calls can take >30s).
_SSE_KEEPALIVE_INTERVAL = 15  # seconds


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


def get_runner() -> Any:
    """Get the OrchestratorRunner from app state."""
    from noa.api.app_state import get_runner

    return get_runner()


def _get_session_factory() -> Any:
    """Get the DB session factory from app state."""
    from noa.api.app_state import get_session_factory

    return get_session_factory()


# Backward-compatible alias for pre-QC3 callers and tests
get_session_factory = _get_session_factory


def get_health_checker() -> Any:
    """Get the HealthChecker from app state."""
    from noa.api.app_state import get_health_checker as _ghc

    return _ghc()


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

    # Default privacy_mode to "external" when omitted (iOS compatibility — H1)
    privacy_mode: Literal["private", "external"] = body.privacy_mode or "external"

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

    # M1: Check idempotency key for duplicate request detection
    idem_key = idempotency_key_ctx.get()
    if idem_key and idem_key in _active_idempotency_keys:
        return JSONResponse(
            status_code=409,
            content={"ok": False, "error": {"code": "DUPLICATE_REQUEST",
                     "message": "Duplicate request (same Idempotency-Key)"}},
        )

    run_id = str(uuid.uuid4())
    thread_id = body.thread_id or str(uuid.uuid4())

    # M1: Register idempotency key as active
    if idem_key:
        import time as _time

        _active_idempotency_keys[idem_key] = _time.monotonic()
        # Prune expired keys
        cutoff = _time.monotonic() - _IDEMPOTENCY_TTL_SECONDS
        expired = [k for k, t in _active_idempotency_keys.items() if t < cutoff]
        for k in expired:
            _active_idempotency_keys.pop(k, None)

    runner = get_runner()

    # W22-H1/H2: Load user settings for agent limits and approvals toggle
    user_settings = await _load_user_settings(user.user_id)

    # MVP-H3: Check private domain availability from HealthChecker
    _checker = get_health_checker()
    private_available: bool = _checker.is_available() if _checker is not None else True

    # MVP-H3: If private domain is requested but unavailable, enqueue the task
    if privacy_mode == "private" and not private_available:
        # MVP-M2: Create Run + Conversation rows so queued request appears on Runs page.
        # Use initial_status="queued" directly — avoids a state machine transition.
        await _make_run_service(
            user_id, thread_id, run_id, privacy_mode, body.message,
            initial_status="queued",
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

    # BE-C3: Verify existing thread belongs to the correct domain
    if body.thread_id is not None:
        domain_error = await _check_thread_domain(
            body.thread_id, user_id, privacy_mode,
        )
        if domain_error is not None:
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": {"code": "DOMAIN_MISMATCH", "message": domain_error},
                },
            )

    async def event_stream() -> Any:
        """Generate SSE events from the runner."""
        # Initial metadata event with run_id and thread_id
        meta = {
            "event_type": "meta",
            "run_id": run_id,
            "thread_id": thread_id,
        }
        yield f"data: {json.dumps(meta)}\n\n"

        if runner is None:
            # No runner configured — return error
            err = {
                "event_type": "error",
                "payload": {"error": "Chat pipeline not configured"},
            }
            yield f"data: {json.dumps(err)}\n\n"
            return

        # Create Conversation + Run rows in DB and get a no-op service for the runner
        run_svc = await _make_run_service(
            user_id, thread_id, run_id, privacy_mode, body.message,
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

        # Persist messages, usage, events, and run status to DB (best-effort)
        await _persist_messages(
            user_id, thread_id, run_id, body.message, response_text, privacy_mode,
        )
        if llm_usage:
            await _record_usage(user_id, run_id, llm_usage)
        await _persist_run_events(run_id, collected_events)
        # If an approval is pending, set run to awaiting_approval so the
        # decide endpoint can resume it after the user approves.
        if has_pending_approval:
            final_status = "awaiting_approval"
        elif response_text:
            final_status = "completed"
        else:
            final_status = "failed"
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
    """
    defaults: dict[str, Any] = {
        "max_tool_calls": 10,
        "max_retries": 3,
        "timeout_seconds": 120,
        "approvals_enabled": True,
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
            }
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load user settings for agent limits")
        return defaults


async def _check_thread_domain(
    thread_id: str,
    user_id: str,
    privacy_mode: str,
) -> str | None:
    """Verify the thread's domain matches the current privacy_mode.

    BE-C3: Returns an error message string if there is a mismatch, None if OK.
    Missing threads are allowed through (will be created with the correct domain).
    """
    factory = _get_session_factory()
    if factory is None:
        # fail-closed: if we can't verify domain, block the request
        return "Domain check unavailable — DB factory not configured"

    try:
        tid = uuid.UUID(thread_id)
    except ValueError:
        return f"Invalid thread_id format: {thread_id!r}"

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return f"Invalid user_id format: {user_id!r}"

    try:
        from sqlalchemy import select

        from noa.db.models.conversation import Conversation

        async with factory() as session:
            result = await session.execute(
                select(Conversation).where(
                    Conversation.id == tid,
                    Conversation.user_id == uid,
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                # Thread doesn't exist yet — will be created with correct domain
                return None
            if conversation.domain != privacy_mode:
                return (
                    f"Thread {thread_id} belongs to domain '{conversation.domain}' "
                    f"but request is in domain '{privacy_mode}'"
                )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to check thread domain for %s", thread_id)
        return None

    return None


async def _make_run_service(
    user_id: str,
    thread_id: str,
    run_id: str,
    privacy_mode: str,
    user_message: str,
    *,
    initial_status: str = "running",
) -> Any:
    """Create Conversation + Run rows in DB, return a no-op service for the runner.

    The runner calls sync methods (update_status, append_event) which
    can't work with AsyncSession.  We create the rows here with
    proper async operations and let the runner use a no-op service.
    Run status updates happen after stream completion.

    MVP-M2: Accepts optional initial_status to support "queued" runs that are
    created before the private domain is available.
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

                session.add(Run(
                    id=uuid.UUID(run_id),
                    user_id=uid,
                    thread_id=tid,
                    status=initial_status,
                    risk_tier="low",
                    privacy_mode=privacy_mode,
                ))
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
            # Reverse to chronological order
            return [
                {"role": m.role, "content": m.content}
                for m in reversed(rows)
                if m.role in ("user", "assistant") and m.content
            ]
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load thread history for %s", thread_id)
        return []


async def _persist_messages(
    user_id: str,
    thread_id: str,
    run_id: str,
    user_message: str,
    assistant_response: str,
    privacy_mode: str = "external",
) -> None:
    """Persist user + assistant messages to the messages table.

    Creates the Conversation row if it doesn't exist yet (new thread from chat).
    BE-C3: New conversations are created with the correct domain.
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
            ))
            # Assistant message (if we got a response)
            if assistant_response:
                session.add(Message(
                    id=uuid.uuid4(),
                    thread_id=tid,
                    user_id=uid,
                    role="assistant",
                    content=assistant_response,
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
            svc = RunService(session=session)
            await svc.update_status(uuid.UUID(run_id), status)
            # Set summary if provided
            if summary:
                result = await session.execute(
                    select(Run).where(Run.id == uuid.UUID(run_id))
                )
                run = result.scalar_one_or_none()
                if run is not None:
                    run.summary = summary
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
        from datetime import UTC, datetime

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
