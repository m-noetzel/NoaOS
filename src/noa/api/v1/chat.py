"""Chat endpoint — web client chat submission with SSE streaming."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from noa.api.middleware import trace_id_ctx
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatRequest(BaseModel):
    """Request body for chat submission."""

    message: str
    thread_id: str | None = None
    privacy_mode: str
    model: str
    provider: str
    temperature: float | None = None
    max_tokens: int | None = None


def get_runner() -> Any:
    """Get the OrchestratorRunner from app state."""
    from noa.api.app_state import get_runner

    return get_runner()


def get_session_factory() -> Any:
    """Get the DB session factory from app state."""
    from noa.api.app_state import get_session_factory

    return get_session_factory()


@router.post("/chat")
async def submit_chat(
    body: ChatRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> StreamingResponse:
    """Submit a chat message and stream SSE events back.

    Creates a Run and Conversation, invokes the OrchestratorRunner,
    and streams events as SSE frames.
    """
    rid = trace_id_ctx.get("")
    run_id = str(uuid.uuid4())
    thread_id = body.thread_id or str(uuid.uuid4())
    user_id = user.get("user_id", user.get("sub", ""))

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

        # Build a lightweight run service mock for event persistence
        # (in production, this would use a real DB session)
        run_svc = _make_run_service(user_id, thread_id, run_id)

        try:
            async for event in runner.run(
                message=body.message,
                run_service=run_svc,
                run_id=run_id,
                privacy_mode=body.privacy_mode,
                model=body.model,
                provider=body.provider,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            err_event = {
                "event_type": "error",
                "payload": {"error": str(exc)},
            }
            yield f"data: {json.dumps(err_event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Trace-ID": rid,
        },
    )


def _make_run_service(
    user_id: str,
    thread_id: str,
    run_id: str,
) -> Any:
    """Create a run service for event persistence.

    Uses the DB session factory if available, otherwise returns
    a no-op service that logs events without persistence.
    """
    factory = get_session_factory()
    if factory is not None:
        try:
            session = factory()
            from noa.runs.service import RunService

            svc = RunService(session)
            # Create the run in DB
            try:
                svc.create_run(
                    user_id=uuid.UUID(user_id),
                    thread_id=uuid.UUID(thread_id),
                    risk_tier="low",
                    privacy_mode="external",
                    summary=None,
                )
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            return svc
        except Exception:  # noqa: BLE001, S110
            pass

    # Fallback: no-op service
    return _NoOpRunService()


class _NoOpRunService:
    """No-op RunService for when DB is not available."""

    def create_run(self, *args: Any, **kwargs: Any) -> None:
        pass

    def update_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def append_event(self, *args: Any, **kwargs: Any) -> None:
        pass
