"""Tests for OI6 — Proactive Memory Extraction (auto_extract tool).

Spec refs: SPEC.md §12.5, §13.2; Phase OI6
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from noa.private_worker.memory_store import MemoryStore
from noa.tools.definitions import TOOL_SCHEMAS, get_anthropic_tools, get_openai_tools
from noa.tools.memory import MemoryTool

# ---------------------------------------------------------------------------
# Tool definition tests
# ---------------------------------------------------------------------------


def test_auto_extract_definition_exists_in_memory_schema() -> None:
    """auto_extract must be a registered function in the memory tool schema."""
    assert "memory" in TOOL_SCHEMAS
    functions = TOOL_SCHEMAS["memory"]["functions"]
    assert "auto_extract" in functions, (
        "auto_extract not found in TOOL_SCHEMAS['memory']['functions']. "
        "OI6 requires this function to be registered."
    )


def test_auto_extract_definition_has_facts_list_parameter() -> None:
    """auto_extract must accept a 'facts' array parameter."""
    func_def = TOOL_SCHEMAS["memory"]["functions"]["auto_extract"]
    params = func_def["parameters"]
    assert "facts" in params["properties"]
    facts_prop = params["properties"]["facts"]
    assert facts_prop["type"] == "array"
    assert facts_prop["items"]["type"] == "string"
    assert "facts" in params["required"]


def test_auto_extract_has_correct_domain_and_risk_tier() -> None:
    """auto_extract must be private domain, low risk."""
    func_def = TOOL_SCHEMAS["memory"]["functions"]["auto_extract"]
    assert func_def["domain"] == "private"
    assert func_def["risk_tier"] == "low"


def test_auto_extract_appears_in_anthropic_tool_list() -> None:
    """memory__auto_extract must appear when memory is in registered tools."""
    tools = get_anthropic_tools(["memory"])
    names = [t["name"] for t in tools]
    assert "memory__auto_extract" in names


def test_auto_extract_appears_in_openai_tool_list() -> None:
    """memory__auto_extract must appear in OpenAI format."""
    tools = get_openai_tools(["memory"])
    names = [t["function"]["name"] for t in tools]
    assert "memory__auto_extract" in names


# ---------------------------------------------------------------------------
# MemoryTool.auto_extract() unit tests
# ---------------------------------------------------------------------------


def _make_rpc_mock(status: str = "stored") -> AsyncMock:
    """Create an RPC mock that returns a 'stored' or 'duplicate' result."""
    mock = AsyncMock()
    mock.return_value = {"status": "ok", "result": {"status": status}}
    return mock


@pytest.mark.asyncio
async def test_auto_extract_stores_multiple_facts() -> None:
    """auto_extract stores each fact in the list via RPC."""
    rpc = _make_rpc_mock("stored")
    tool = MemoryTool(rpc_client=rpc)

    result = await tool.auto_extract(facts=["I am vegetarian", "I prefer short answers"])

    assert result["status"] == "ok"
    assert result["stored"] == 2
    assert result["skipped"] == 0
    assert rpc.call_count == 2

    # Verify the RPC payload sets auto_extracted=True
    for call_args in rpc.call_args_list:
        payload = call_args[0][0]["payload"]
        assert payload["auto_extracted"] is True
        assert payload["category"] == "general"


@pytest.mark.asyncio
async def test_auto_extract_empty_list_returns_zero() -> None:
    """auto_extract with empty list returns 0 stored without calling RPC."""
    rpc = _make_rpc_mock()
    tool = MemoryTool(rpc_client=rpc)

    result = await tool.auto_extract(facts=[])

    assert result["status"] == "ok"
    assert result["stored"] == 0
    assert result["skipped"] == 0
    rpc.assert_not_called()


@pytest.mark.asyncio
async def test_auto_extract_single_fact() -> None:
    """auto_extract with a single-element list stores one fact."""
    rpc = _make_rpc_mock("stored")
    tool = MemoryTool(rpc_client=rpc)

    result = await tool.auto_extract(facts=["My meeting is every Tuesday at 10am"])

    assert result["stored"] == 1
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_auto_extract_skips_duplicates() -> None:
    """auto_extract counts RPC-reported duplicates as skipped."""
    rpc = _make_rpc_mock("duplicate")
    tool = MemoryTool(rpc_client=rpc)

    result = await tool.auto_extract(facts=["I am vegetarian"])

    assert result["stored"] == 0
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_auto_extract_skips_blank_strings() -> None:
    """Blank/whitespace strings in facts list are skipped without RPC call."""
    rpc = _make_rpc_mock("stored")
    tool = MemoryTool(rpc_client=rpc)

    result = await tool.auto_extract(facts=["", "  ", "I prefer dark mode"])

    assert result["stored"] == 1
    assert result["skipped"] == 2
    assert rpc.call_count == 1


@pytest.mark.asyncio
async def test_auto_extract_strips_whitespace_from_facts() -> None:
    """Fact text is stripped of leading/trailing whitespace before storage."""
    rpc = _make_rpc_mock("stored")
    tool = MemoryTool(rpc_client=rpc)

    await tool.auto_extract(facts=["  I prefer early mornings  "])

    call_payload = rpc.call_args[0][0]["payload"]
    assert call_payload["fact"] == "I prefer early mornings"


# ---------------------------------------------------------------------------
# Integration test: MemoryStore stores auto_extracted facts with pending status
# ---------------------------------------------------------------------------


def test_memory_store_auto_extracted_fact_has_pending_status() -> None:
    """Facts stored with auto_extracted=True land in pending status."""
    store = MemoryStore(data_dir=None)

    fact_id = store.store(
        fact="I prefer concise answers",
        category="preference",
        embedding=[],
        source_thread_id="thread-1",
        auto_extracted=True,
    )

    assert fact_id is not None
    stored_fact = store.get_by_id(fact_id)
    assert stored_fact is not None
    assert stored_fact["status"] == "pending"
    assert stored_fact["auto_extracted"] is True


def test_memory_store_auto_extracted_fact_not_returned_by_recall() -> None:
    """Pending auto-extracted facts must NOT appear in recall results."""
    store = MemoryStore(data_dir=None)

    store.store(
        fact="I am vegetarian",
        category="preference",
        embedding=[1.0, 0.0],
        source_thread_id="",
        auto_extracted=True,
    )

    # recall only returns approved facts
    results = store.recall(query_embedding=[1.0, 0.0], n_results=10)
    fact_texts = [r["fact"] for r in results]
    assert "I am vegetarian" not in fact_texts


def test_memory_store_auto_extracted_fact_appears_after_approval() -> None:
    """After approval, auto-extracted facts are returned by recall."""
    store = MemoryStore(data_dir=None)

    fact_id = store.store(
        fact="I like hiking",
        category="preference",
        embedding=[1.0, 0.0],
        source_thread_id="",
        auto_extracted=True,
    )
    assert fact_id is not None

    # Approve the fact
    store.update_status(fact_id, "approved")

    results = store.recall(query_embedding=[1.0, 0.0], n_results=10)
    fact_texts = [r["fact"] for r in results]
    assert "I like hiking" in fact_texts


# ---------------------------------------------------------------------------
# Integration: dispatch through MemoryTool.execute()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_tool_execute_dispatches_auto_extract() -> None:
    """MemoryTool.execute() correctly routes 'auto_extract' function calls."""
    rpc = _make_rpc_mock("stored")
    tool = MemoryTool(rpc_client=rpc)

    result = await tool.execute(
        function="auto_extract",
        args={"facts": ["I work best in the mornings"]},
    )

    assert result["status"] == "ok"
    assert result["stored"] == 1
