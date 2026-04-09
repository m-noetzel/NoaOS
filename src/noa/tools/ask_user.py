"""Ask-user tool — agent calls this to request structured user input.

OV8: The ask_user tool uses LangGraph's interrupt() mechanism to pause
the graph and collect user input, resuming with the user's response.
It emits an ``ask_user`` SSE event (not ``approval_requested``).

Spec refs: SPEC.md §22.1, §22.2
"""

from __future__ import annotations

from langgraph.types import interrupt


def ask_user_tool(
    *,
    question: str,
    options: list[str] | None = None,
    allow_freetext: bool = True,
) -> dict[str, str]:
    """Pause the graph and ask the user for input.

    Calls LangGraph ``interrupt()`` with a payload that the runner
    differentiates from approval interrupts (``ask_user: True`` key).
    The graph resumes via ``Command(resume={"response": "user's choice"})``.

    Args:
        question: The question to display to the user.
        options: Up to 3 suggested options (rendered as buttons in the UI).
        allow_freetext: Whether to show a freetext input field.

    Returns:
        Dict with ``user_response`` key containing the user's answer.
    """
    validated_options: list[str] = (options or [])[:3]

    result = interrupt({
        "ask_user": True,
        "question": question,
        "options": validated_options,
        "allow_freetext": allow_freetext,
    })

    # result comes from Command(resume={"response": "user's choice"})
    if isinstance(result, dict):
        user_response = result.get("response", "")
    else:
        user_response = str(result)

    return {"user_response": user_response}
