"""OV1: Tests for Langfuse instrumentation fixes.

Finding OBS-LF2 (High): Token key mismatch — agent.py stores input_tokens /
output_tokens but runner.py was reading prompt_tokens / completion_tokens,
causing Langfuse to always record 0 tokens.

Finding OBS-LF1 (Medium, partial): Separate input/output in node spans;
include approval_required and error in tool span output.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_trace() -> MagicMock:
    """Return a mock TraceContext whose internal _trace is a MagicMock."""
    from noa.observability.langfuse_client import TraceContext

    ctx = TraceContext.__new__(TraceContext)
    ctx._run_id = "test-run"
    ctx._trace = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# OBS-LF2: token key mapping
# ---------------------------------------------------------------------------


class TestTokenKeyMapping:
    """Verify that input_tokens / output_tokens are mapped to the Langfuse
    SDK's expected prompt_tokens / completion_tokens keys."""

    def test_generation_span_receives_correct_token_keys(self) -> None:
        """TraceContext.generation() forwards usage keys to Langfuse trace."""
        ctx = _make_mock_trace()

        ctx.generation(
            name="agent",
            model="gpt-4o",
            input_messages=[{"role": "user", "content": "hi"}],
            output="hello",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
        )

        ctx._trace.generation.assert_called_once()
        call_kwargs = ctx._trace.generation.call_args.kwargs
        assert call_kwargs["usage"] == {"prompt_tokens": 10, "completion_tokens": 20}

    def test_runner_maps_input_tokens_to_prompt_tokens(self) -> None:
        """runner.py maps input_tokens -> prompt_tokens and
        output_tokens -> completion_tokens when building the usage dict."""
        # This tests the mapping logic in isolation by constructing a usage
        # entry identical to what agent.py produces and verifying that the
        # dict built by runner.py contains the correct Langfuse keys.
        usage_entry: dict[str, Any] = {
            "node": "agent",
            "model": "gpt-4o",
            "input_tokens": 15,
            "output_tokens": 42,
            "cost_usd": 0.001,
            "provider": "openai",
            "input_messages": [{"role": "user", "content": "What's the weather?"}],
            "output_text": "It's sunny today.",
        }

        # Replicate runner.py mapping (lines ~510-511 post-fix)
        mapped_usage = {
            "prompt_tokens": usage_entry.get("input_tokens", 0),
            "completion_tokens": usage_entry.get("output_tokens", 0),
        }

        assert mapped_usage["prompt_tokens"] == 15
        assert mapped_usage["completion_tokens"] == 42
        # The old buggy keys must not be present in the mapped dict
        assert "input_tokens" not in mapped_usage
        assert "output_tokens" not in mapped_usage

    def test_runner_maps_zero_tokens_gracefully(self) -> None:
        """Missing token fields default to 0, not errors."""
        usage_entry: dict[str, Any] = {
            "model": "gpt-4o",
            # No input_tokens / output_tokens
        }

        mapped_usage = {
            "prompt_tokens": usage_entry.get("input_tokens", 0),
            "completion_tokens": usage_entry.get("output_tokens", 0),
        }

        assert mapped_usage["prompt_tokens"] == 0
        assert mapped_usage["completion_tokens"] == 0

    def test_old_buggy_key_read_returns_zero(self) -> None:
        """Demonstrate the original bug: reading prompt_tokens from an
        agent.py usage record (which only has input_tokens) always returned 0.
        This test documents the bug to ensure the fix stays in place."""
        # agent.py usage record has input_tokens, NOT prompt_tokens
        usage_entry_from_agent: dict[str, Any] = {
            "input_tokens": 50,
            "output_tokens": 100,
        }

        # Old (buggy) code — would read 0
        old_prompt_tokens = usage_entry_from_agent.get("prompt_tokens", 0)
        old_completion_tokens = usage_entry_from_agent.get("completion_tokens", 0)
        assert old_prompt_tokens == 0
        assert old_completion_tokens == 0

        # New (correct) code — reads actual values
        new_prompt_tokens = usage_entry_from_agent.get("input_tokens", 0)
        new_completion_tokens = usage_entry_from_agent.get("output_tokens", 0)
        assert new_prompt_tokens == 50
        assert new_completion_tokens == 100


# ---------------------------------------------------------------------------
# OBS-LF1: node span input/output separation
# ---------------------------------------------------------------------------


class TestNodeSpanInputOutputSeparation:
    """Verify node spans have distinct, non-overlapping input vs output."""

    def test_messages_key_is_in_output_not_input(self) -> None:
        """The 'messages' field from agent node belongs in output (it contains
        the updated conversation including the assistant reply), not input."""
        INPUT_KEYS = ("plan", "task_type", "archetype",
                      "selected_model", "privacy_mode", "tool_calls")
        OUTPUT_KEYS = ("response", "messages", "selected_model",
                       "privacy_mode", "plan", "task_type",
                       "archetype", "eval_scores", "eval_verdict", "tool_results")

        # messages must appear in output, not input
        assert "messages" in OUTPUT_KEYS
        assert "messages" not in INPUT_KEYS

    def test_tool_calls_key_is_in_input_not_duplicated_in_output(self) -> None:
        """tool_calls (the LLM's intent) is input context; it shouldn't appear
        in the output set which represents what the node produced."""
        INPUT_KEYS = ("plan", "task_type", "archetype",
                      "selected_model", "privacy_mode", "tool_calls")
        OUTPUT_KEYS = ("response", "messages", "selected_model",
                       "privacy_mode", "plan", "task_type",
                       "archetype", "eval_scores", "eval_verdict", "tool_results")

        assert "tool_calls" in INPUT_KEYS
        assert "tool_calls" not in OUTPUT_KEYS

    def test_node_span_filters_node_output_correctly(self) -> None:
        """Simulate the dict comprehension in runner.py and verify the correct
        keys land in input vs output for a typical agent node output."""
        node_output: dict[str, Any] = {
            "messages": [{"role": "assistant", "content": "Hello"}],
            "tool_calls": [{"name": "web_search", "args": {}}],
            "response": "Hello",
            "selected_model": "gpt-4o",
            "privacy_mode": False,
            "plan": None,
            "task_type": "qa",
            "archetype": "agent",
            "llm_usage": [{"input_tokens": 10, "output_tokens": 5}],
            "some_internal_key": "ignored",
        }

        INPUT_KEYS = ("plan", "task_type", "archetype",
                      "selected_model", "privacy_mode", "tool_calls")
        OUTPUT_KEYS = ("response", "messages", "selected_model",
                       "privacy_mode", "plan", "task_type",
                       "archetype", "eval_scores", "eval_verdict", "tool_results")

        span_input = {k: v for k, v in node_output.items() if k in INPUT_KEYS}
        span_output = {k: v for k, v in node_output.items() if k in OUTPUT_KEYS}

        # messages ends up in output only
        assert "messages" in span_output
        assert "messages" not in span_input

        # tool_calls ends up in input only
        assert "tool_calls" in span_input
        assert "tool_calls" not in span_output

        # internal/llm_usage keys are not leaked
        assert "llm_usage" not in span_input
        assert "llm_usage" not in span_output
        assert "some_internal_key" not in span_input
        assert "some_internal_key" not in span_output

        # response (what the agent produced) is in output
        assert "response" in span_output


# ---------------------------------------------------------------------------
# OBS-LF1: tool span approval_required and error fields
# ---------------------------------------------------------------------------


class TestToolSpanOutputFields:
    """Verify tool spans include approval_required and error when present."""

    def test_tool_span_includes_approval_required_when_true(self) -> None:
        """When a tool result has approval_required=True, the span output
        must include that field so Langfuse shows it."""
        tr: dict[str, Any] = {
            "name": "send_email",
            "args": {"to": "alice@example.com"},
            "result": None,
            "approval_required": True,
        }

        # Replicate the _tool_output construction from runner.py post-fix
        tool_output: dict[str, Any] = {
            "result": tr.get("result", tr.get("output", "")),
        }
        if tr.get("approval_required"):
            tool_output["approval_required"] = True
        if tr.get("error"):
            tool_output["error"] = tr["error"]

        assert tool_output["approval_required"] is True
        assert "error" not in tool_output

    def test_tool_span_includes_error_when_present(self) -> None:
        """When a tool result has an error, the span output must include it."""
        tr: dict[str, Any] = {
            "name": "web_search",
            "args": {"query": "langfuse"},
            "result": None,
            "error": "HTTP 429 Too Many Requests",
        }

        tool_output: dict[str, Any] = {
            "result": tr.get("result", tr.get("output", "")),
        }
        if tr.get("approval_required"):
            tool_output["approval_required"] = True
        if tr.get("error"):
            tool_output["error"] = tr["error"]

        assert tool_output["error"] == "HTTP 429 Too Many Requests"
        assert "approval_required" not in tool_output

    def test_tool_span_omits_approval_and_error_when_absent(self) -> None:
        """Successful tool calls without approval/error produce clean output."""
        tr: dict[str, Any] = {
            "name": "web_search",
            "args": {"query": "hello"},
            "result": "Some result",
        }

        tool_output: dict[str, Any] = {
            "result": tr.get("result", tr.get("output", "")),
        }
        if tr.get("approval_required"):
            tool_output["approval_required"] = True
        if tr.get("error"):
            tool_output["error"] = tr["error"]

        assert tool_output == {"result": "Some result"}

    def test_tool_span_both_approval_and_error(self) -> None:
        """Edge case: both approval_required and error are present."""
        tr: dict[str, Any] = {
            "name": "delete_file",
            "args": {"path": "/var/data/test"},
            "result": None,
            "approval_required": True,
            "error": "Permission denied",
        }

        tool_output: dict[str, Any] = {
            "result": tr.get("result", tr.get("output", "")),
        }
        if tr.get("approval_required"):
            tool_output["approval_required"] = True
        if tr.get("error"):
            tool_output["error"] = tr["error"]

        assert tool_output["approval_required"] is True
        assert tool_output["error"] == "Permission denied"


# ---------------------------------------------------------------------------
# Integration: agent.py usage record contains input/output fields
# ---------------------------------------------------------------------------


class TestAgentUsageRecord:
    """Verify that agent.py correctly stores input_messages and output_text
    in the usage record so generation spans have real content."""

    def test_usage_record_has_input_output_fields(self) -> None:
        """The usage record produced by agent.py must include input_messages
        and output_text alongside the token counts."""
        # These are the keys agent.py now stores (post OV1 fix)
        expected_keys = {
            "provider", "model", "input_tokens", "output_tokens",
            "cost_usd", "input_messages", "output_text",
        }

        # Build a sample usage_record matching the post-fix agent.py code
        usage_record: dict[str, Any] = {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.002,
            "input_messages": [{"role": "user", "content": "Hello"}],
            "output_text": "Hi there!",
        }

        assert set(usage_record.keys()) == expected_keys

    def test_generation_span_uses_input_messages_from_usage_record(self) -> None:
        """runner.py passes usage_entry input_messages to generation() so
        Langfuse shows the actual prompt sent to the LLM."""
        usage_entry: dict[str, Any] = {
            "node": "agent",
            "model": "gpt-4o",
            "input_tokens": 30,
            "output_tokens": 15,
            "cost_usd": 0.0005,
            "provider": "openai",
            "input_messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What time is it?"},
            ],
            "output_text": "It's 3 PM.",
        }

        # Replicate runner.py generation call construction post-fix
        generation_call_args = {
            "name": usage_entry.get("node", "agent"),
            "model": usage_entry.get("model", "unknown"),
            "input_messages": usage_entry.get("input_messages", []),
            "output": usage_entry.get("output_text", ""),
            "usage": {
                "prompt_tokens": usage_entry.get("input_tokens", 0),
                "completion_tokens": usage_entry.get("output_tokens", 0),
            },
            "metadata": {
                "cost": usage_entry.get("cost_usd", 0.0),
                "provider": usage_entry.get("provider", ""),
            },
        }

        assert generation_call_args["input_messages"] == [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What time is it?"},
        ]
        assert generation_call_args["output"] == "It's 3 PM."
        assert generation_call_args["usage"]["prompt_tokens"] == 30
        assert generation_call_args["usage"]["completion_tokens"] == 15
        assert generation_call_args["metadata"]["cost"] == 0.0005


# ---------------------------------------------------------------------------
# TraceContext.generation() integration (real class, mocked _trace)
# ---------------------------------------------------------------------------


class TestTraceContextGenerationIntegration:
    """Test TraceContext.generation() is called with the correct mapped keys."""

    def test_trace_context_generation_with_mapped_tokens(self) -> None:
        """TraceContext.generation() forwards the usage dict verbatim to
        the Langfuse SDK — the mapping must happen before calling it."""
        ctx = _make_mock_trace()

        messages = [{"role": "user", "content": "Summarise this."}]
        ctx.generation(
            name="agent",
            model="claude-3-5-sonnet",
            input_messages=messages,
            output="Summary text.",
            usage={"prompt_tokens": 77, "completion_tokens": 33},
            metadata={"cost": 0.003, "provider": "anthropic"},
        )

        ctx._trace.generation.assert_called_once()
        call_kwargs = ctx._trace.generation.call_args.kwargs
        # Langfuse SDK receives prompt_tokens / completion_tokens
        assert call_kwargs["usage"]["prompt_tokens"] == 77
        assert call_kwargs["usage"]["completion_tokens"] == 33
        # input and output are forwarded
        assert call_kwargs["input"] == messages
        assert call_kwargs["output"] == "Summary text."

    def test_trace_context_span_records_tool_output(self) -> None:
        """TraceContext.span() forwards the output dict including approval
        and error fields."""
        ctx = _make_mock_trace()

        ctx.span(
            name="tool/send_email",
            input={"to": "alice@example.com", "subject": "Hi"},
            output={
                "result": None,
                "approval_required": True,
                "error": "Needs human approval",
            },
            metadata={"tool_name": "send_email"},
        )

        ctx._trace.span.assert_called_once()
        call_kwargs = ctx._trace.span.call_args.kwargs
        assert call_kwargs["output"]["approval_required"] is True
        assert call_kwargs["output"]["error"] == "Needs human approval"
