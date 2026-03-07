"""Add performance indexes per QC5/H2.

Revision ID: 006
Revises: 005
Create Date: 2026-03-07

Adds indexes on frequently queried columns:
- audit_log(timestamp), audit_log(user_id), audit_log(trace_id)
- messages(thread_id)
- run_events(run_id)
- usage_stats(user_id, timestamp)
- task_queue(status, queued_at)
"""

from __future__ import annotations

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_trace_id", "audit_log", ["trace_id"])
    op.create_index("ix_messages_thread_id", "messages", ["thread_id"])
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_index(
        "ix_usage_stats_user_id_timestamp",
        "usage_stats",
        ["user_id", "timestamp"],
    )
    op.create_index(
        "ix_task_queue_status_queued_at",
        "task_queue",
        ["status", "queued_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_queue_status_queued_at", "task_queue")
    op.drop_index("ix_usage_stats_user_id_timestamp", "usage_stats")
    op.drop_index("ix_run_events_run_id", "run_events")
    op.drop_index("ix_messages_thread_id", "messages")
    op.drop_index("ix_audit_log_trace_id", "audit_log")
    op.drop_index("ix_audit_log_user_id", "audit_log")
    op.drop_index("ix_audit_log_timestamp", "audit_log")
