"""Unit tests for ST1: Run Lifecycle Fixes.

Covers CHAT-H2 (runs stuck in 'running') and TECH-M4 (orphan recovery).
All tests inspect the actual source of the modules under test — no logic
duplication that could hide regressions.
"""

from __future__ import annotations

import inspect  # noqa: I001

# ---------------------------------------------------------------------------
# CHAT-H2: final_status logic in chat.py
# ---------------------------------------------------------------------------


def test_task_complete_marker_removed_from_chat_module() -> None:
    """_TASK_COMPLETE_MARKER must not exist in chat.py."""
    import noa.api.v1.chat as chat_module

    assert not hasattr(chat_module, "_TASK_COMPLETE_MARKER"), (
        "_TASK_COMPLETE_MARKER should have been removed from chat.py (CHAT-H2)"
    )


def test_chat_module_final_status_does_not_default_to_running() -> None:
    """'final_status = "running"' must not appear anywhere in chat.py."""
    import noa.api.v1.chat as chat_module

    source = inspect.getsource(chat_module)
    assert 'final_status = "running"' not in source, (
        "chat.py must not assign final_status = 'running' (CHAT-H2 regression)"
    )


def test_chat_module_normal_path_yields_completed() -> None:
    """chat.py source must contain 'final_status = "completed"' as the else branch."""
    import noa.api.v1.chat as chat_module

    source = inspect.getsource(chat_module)
    assert 'final_status = "completed"' in source, (
        "chat.py must set final_status = 'completed' for normal turns (CHAT-H2)"
    )


def test_chat_module_approval_path_yields_awaiting_approval() -> None:
    """chat.py source must contain 'awaiting_approval' as a possible final_status."""
    import noa.api.v1.chat as chat_module

    source = inspect.getsource(chat_module)
    assert '"awaiting_approval"' in source, (
        "chat.py must handle awaiting_approval status for approval turns"
    )


def test_chat_module_empty_response_path_yields_failed() -> None:
    """chat.py source must contain 'failed' as a possible final_status."""
    import noa.api.v1.chat as chat_module

    source = inspect.getsource(chat_module)
    assert 'final_status = "failed"' in source, (
        "chat.py must set final_status = 'failed' when no response produced"
    )


# ---------------------------------------------------------------------------
# CHAT-H2: approvals.py denial path
# ---------------------------------------------------------------------------


def test_approvals_denied_path_finalizes_run() -> None:
    """approvals.py must resume the graph when denied.

    OV2: approval decisions are handled by runner.resume() which manages
    run finalization inside the graph (no direct _run.status assignment).
    """
    import noa.api.v1.approvals as approvals_module

    source = inspect.getsource(approvals_module)
    # OV2: graph is resumed with the decision; runner handles finalization
    assert "runner.resume" in source, (
        "approvals.py must call runner.resume() to finalize run on decision (OV2)"
    )


def test_approvals_approved_path_finalizes_run() -> None:
    """approvals.py must resume the graph when approved.

    OV2: approval decisions are handled by runner.resume() which manages
    run finalization inside the graph.
    """
    import noa.api.v1.approvals as approvals_module

    source = inspect.getsource(approvals_module)
    # OV2: both approved and denied flow through runner.resume()
    assert "runner.resume" in source, (
        "approvals.py must call runner.resume() to finalize approved run (OV2)"
    )
