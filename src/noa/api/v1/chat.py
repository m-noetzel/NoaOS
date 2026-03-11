"""Chat endpoint — web client chat submission with SSE streaming."""

from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from noa.api.middleware import idempotency_key_ctx, trace_id_ctx
from noa.auth.middleware import AuthUser, require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# M1: In-memory idempotency key tracking (TTL-based cleanup)
_active_idempotency_keys: dict[str, float] = {}
_IDEMPOTENCY_TTL_SECONDS = 300  # 5 minutes


class ChatRequest(BaseModel):
    """Request body for chat submission."""

    message: str
    thread_id: str | None = None
    privacy_mode: str
    model: str
    provider: str
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


@router.post("/chat")
async def submit_chat(
    body: ChatRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> StreamingResponse:
    """Submit a chat message and stream SSE events back.

    Creates a Run and Conversation, invokes the OrchestratorRunner,
    and streams events as SSE frames.
    """
    rid = trace_id_ctx.get("")

    # M1: Check idempotency key for duplicate request detection
    idem_key = idempotency_key_ctx.get()
    if idem_key and idem_key in _active_idempotency_keys:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=409,
            content={"ok": False, "error": {"code": "DUPLICATE_REQUEST",
                     "message": "Duplicate request (same Idempotency-Key)"}},
        )

    run_id = str(uuid.uuid4())
    thread_id = body.thread_id or str(uuid.uuid4())
    user_id = str(user.user_id)

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
            user_id, thread_id, run_id, body.privacy_mode, body.message,
        )

        llm_usage: list[dict[str, Any]] = []
        response_text = ""

        try:
            async for event in runner.run(
                message=body.message,
                run_service=run_svc,
                run_id=run_id,
                privacy_mode=body.privacy_mode,
                model=body.model,
                provider=body.provider,
                system_prompt=body.system_prompt,
            ):
                # Capture response and llm_usage from result_ready for persistence
                if event.get("event_type") == "result_ready":
                    payload = event.get("payload", {})
                    llm_usage = payload.get("llm_usage", [])
                    response_text = payload.get("response", "")
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            err_event = {
                "event_type": "error",
                "payload": {"error": str(exc)},
            }
            yield f"data: {json.dumps(err_event)}\n\n"

        # Persist messages, usage, and run status to DB (best-effort)
        await _persist_messages(user_id, thread_id, run_id, body.message, response_text)
        if llm_usage:
            await _record_usage(user_id, run_id, llm_usage)
        await _update_run_status(
            run_id, "completed" if response_text else "failed",
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


async def _make_run_service(
    user_id: str,
    thread_id: str,
    run_id: str,
    privacy_mode: str,
    user_message: str,
) -> Any:
    """Create Conversation + Run rows in DB, return a no-op service for the runner.

    The runner calls sync methods (update_status, append_event) which
    can't work with AsyncSession.  We create the rows here with
    proper async operations and let the runner use a no-op service.
    Run status updates happen after stream completion.
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
                if result.scalar_one_or_none() is None:
                    title = user_message[:50].strip() or "New thread"
                    session.add(Conversation(id=tid, user_id=uid, title=title))

                session.add(Run(
                    id=uuid.UUID(run_id),
                    user_id=uid,
                    thread_id=tid,
                    status="running",
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


async def _persist_messages(
    user_id: str,
    thread_id: str,
    run_id: str,
    user_message: str,
    assistant_response: str,
) -> None:
    """Persist user + assistant messages to the messages table.

    Creates the Conversation row if it doesn't exist yet (new thread from chat).
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
            if result.scalar_one_or_none() is None:
                # Derive title from first ~50 chars of user message
                title = user_message[:50].strip() or "New thread"
                session.add(Conversation(id=tid, user_id=uid, title=title))

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


async def _update_run_status(run_id: str, status: str) -> None:
    """Update run status in DB (best-effort)."""
    factory = _get_session_factory()
    if factory is None:
        return

    try:
        from datetime import UTC, datetime

        from sqlalchemy import update

        from noa.db.models.run import Run

        async with factory() as session:
            await session.execute(
                update(Run)
                .where(Run.id == uuid.UUID(run_id))
                .values(status=status, updated_at=datetime.now(UTC))
            )
            await session.commit()
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
