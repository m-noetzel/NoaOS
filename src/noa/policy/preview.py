"""Dry-run preview generation — SPEC.md §19.2."""

from __future__ import annotations

from typing import Any

# Actions that get previews (Medium and High risk create/send actions)
_PREVIEW_ACTIONS = frozenset(
    [
        "send_email",
        "create_calendar_event",
        "update_calendar_event",
        "create_notion_page",
        "update_notion_page",
        "delete_email",
        "delete_calendar_event",
        "delete_notion_page",
    ]
)


def generate_preview(action: str, args: dict[str, Any]) -> str | None:
    """Generate a dry-run preview for an action per §19.2.

    Returns a human-readable preview string, or None if no preview
    is needed (Low risk actions).
    """
    if action not in _PREVIEW_ACTIONS:
        return None

    if action == "send_email":
        to = args.get("to", "unknown")
        subject = args.get("subject", "(no subject)")
        body = args.get("body", "")
        return (
            f"Send email:\n"
            f"  To: {to}\n"
            f"  Subject: {subject}\n"
            f"  Body: {body[:200]}"
        )

    if action in ("create_calendar_event", "update_calendar_event"):
        title = args.get("title", "Untitled")
        start = args.get("start", "")
        end = args.get("end", "")
        return (
            f"Calendar event:\n"
            f"  Title: {title}\n"
            f"  Start: {start}\n"
            f"  End: {end}"
        )

    if action in ("create_notion_page", "update_notion_page"):
        title = args.get("title", "Untitled")
        parent = args.get("parent", "")
        return (
            f"Notion page:\n"
            f"  Title: {title}\n"
            f"  Parent: {parent}"
        )

    if action.startswith("delete_"):
        item_type = action.replace("delete_", "")
        item_id = args.get(
            f"{item_type}_id", args.get("id", "unknown"),
        )
        return f"Delete {item_type}:\n  ID: {item_id}"

    return f"Action: {action}\n  Args: {args}"
