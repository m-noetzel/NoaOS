"""Tests for DI1 Task Classifier Node."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from noa.orchestrator.nodes.classifier import (
    TASK_TYPES,
    _parse_task_type,
    classifier_node,
)

# ---------------------------------------------------------------------------
# _parse_task_type unit tests
# ---------------------------------------------------------------------------


def test_parse_task_type_valid_json_simple_utility():
    result = _parse_task_type('{"task_type": "simple_utility", "confidence": 0.9}')
    assert result == "simple_utility"


def test_parse_task_type_valid_json_execution():
    result = _parse_task_type('{"task_type": "execution", "confidence": 0.85}')
    assert result == "execution"


def test_parse_task_type_valid_json_research():
    result = _parse_task_type('{"task_type": "research", "confidence": 0.7}')
    assert result == "research"


def test_parse_task_type_valid_json_decision_intelligence():
    result = _parse_task_type('{"task_type": "decision_intelligence", "confidence": 0.8}')
    assert result == "decision_intelligence"


def test_parse_task_type_malformed_json_falls_back_to_execution():
    result = _parse_task_type("not json at all")
    assert result == "execution"


def test_parse_task_type_empty_string_falls_back_to_execution():
    result = _parse_task_type("")
    assert result == "execution"


def test_parse_task_type_json_with_unknown_type_falls_back_to_execution():
    result = _parse_task_type('{"task_type": "unknown_type", "confidence": 0.9}')
    assert result == "execution"


def test_parse_task_type_json_missing_task_type_field():
    result = _parse_task_type('{"confidence": 0.9}')
    assert result == "execution"


def test_parse_task_type_text_contains_simple_utility():
    result = _parse_task_type("I think this is simple_utility based on the context")
    assert result == "simple_utility"


def test_parse_task_type_text_contains_research():
    result = _parse_task_type("This looks like a research task to me")
    assert result == "research"


def test_parse_task_type_text_contains_decision_intelligence():
    result = _parse_task_type("Classified as decision_intelligence")
    assert result == "decision_intelligence"


def test_parse_task_type_json_embedded_in_surrounding_text():
    content = 'Sure! Here is my answer: {"task_type": "research", "confidence": 0.75} done.'
    result = _parse_task_type(content)
    assert result == "research"


def test_parse_task_type_covers_all_task_types():
    for tt in TASK_TYPES:
        result = _parse_task_type(f'{{"task_type": "{tt}", "confidence": 0.9}}')
        assert result == tt


# ---------------------------------------------------------------------------
# classifier_node async tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_node_empty_messages_returns_simple_utility():
    state: dict[str, Any] = {"messages": [], "model_config": {}}
    result = await classifier_node(state)  # type: ignore[arg-type]
    assert result == {"task_type": "simple_utility"}


@pytest.mark.asyncio
async def test_classifier_node_no_messages_key_returns_simple_utility():
    state: dict[str, Any] = {"model_config": {}}
    result = await classifier_node(state)  # type: ignore[arg-type]
    assert result == {"task_type": "simple_utility"}


@pytest.mark.asyncio
async def test_classifier_node_no_user_message_returns_simple_utility():
    state: dict[str, Any] = {
        "messages": [{"role": "assistant", "content": "Hello!"}],
        "model_config": {},
    }
    result = await classifier_node(state)  # type: ignore[arg-type]
    assert result == {"task_type": "simple_utility"}


@pytest.mark.asyncio
async def test_classifier_node_model_none_returns_execution():
    state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Do something"}],
        "model_config": {"classifier": "none"},
    }
    result = await classifier_node(state)  # type: ignore[arg-type]
    assert result == {"task_type": "execution"}


@pytest.mark.asyncio
async def test_classifier_node_uses_model_from_model_config():
    """Classifier uses the model specified in model_config.classifier."""
    captured_model: list[str] = []

    class FakeLLMResponse:
        content = '{"task_type": "research", "confidence": 0.8}'
        tool_calls: list = []

    async def fake_invoke_llm(model: str, messages: list, **kwargs: Any) -> FakeLLMResponse:
        captured_model.append(model)
        return FakeLLMResponse()

    state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Compare these options for me"}],
        "model_config": {"classifier": "openai/gpt-4o-mini"},
    }

    with patch("noa.orchestrator.nodes.classifier.invoke_llm", side_effect=fake_invoke_llm):
        result = await classifier_node(state)  # type: ignore[arg-type]

    assert result == {"task_type": "research"}
    assert captured_model == ["openai/gpt-4o-mini"]


@pytest.mark.asyncio
async def test_classifier_node_passes_empty_tools_list():
    """Classifier invokes invoke_llm with an empty tools list."""
    captured_kwargs: list[dict[str, Any]] = []

    class FakeLLMResponse:
        content = '{"task_type": "execution", "confidence": 0.9}'
        tool_calls: list = []

    async def fake_invoke_llm(model: str, messages: list, **kwargs: Any) -> FakeLLMResponse:
        captured_kwargs.append(kwargs)
        return FakeLLMResponse()

    state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Send an email to Alice"}],
        "model_config": {"classifier": "openai/gpt-4o-mini"},
    }

    with patch("noa.orchestrator.nodes.classifier.invoke_llm", side_effect=fake_invoke_llm):
        await classifier_node(state)  # type: ignore[arg-type]

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["tools"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("task_type", TASK_TYPES)
async def test_classifier_node_returns_each_task_type(task_type: str):
    """classifier_node correctly returns each valid task type from LLM response."""

    class FakeLLMResponse:
        content = f'{{"task_type": "{task_type}", "confidence": 0.9}}'
        tool_calls: list = []

    async def fake_invoke_llm(*args: Any, **kwargs: Any) -> FakeLLMResponse:
        return FakeLLMResponse()

    state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Some message"}],
        "model_config": {"classifier": "openai/gpt-4o-mini"},
    }

    with patch("noa.orchestrator.nodes.classifier.invoke_llm", side_effect=fake_invoke_llm):
        result = await classifier_node(state)  # type: ignore[arg-type]

    assert result == {"task_type": task_type}


@pytest.mark.asyncio
async def test_classifier_node_llm_failure_defaults_to_execution():
    """When invoke_llm raises, classifier falls back to 'execution'."""

    async def failing_invoke_llm(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("LLM unavailable")

    state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Do something complex"}],
        "model_config": {"classifier": "openai/gpt-4o-mini"},
    }

    with patch("noa.orchestrator.nodes.classifier.invoke_llm", side_effect=failing_invoke_llm):
        result = await classifier_node(state)  # type: ignore[arg-type]

    assert result == {"task_type": "execution"}


@pytest.mark.asyncio
async def test_classifier_node_fallback_model_when_config_missing():
    """When model_config has no classifier key, falls back to openai/gpt-4o-mini."""
    captured_model: list[str] = []

    class FakeLLMResponse:
        content = '{"task_type": "simple_utility", "confidence": 0.95}'
        tool_calls: list = []

    async def fake_invoke_llm(model: str, messages: list, **kwargs: Any) -> FakeLLMResponse:
        captured_model.append(model)
        return FakeLLMResponse()

    state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "What time is it?"}],
        "model_config": {},  # No "classifier" key
    }

    with patch("noa.orchestrator.nodes.classifier.invoke_llm", side_effect=fake_invoke_llm):
        result = await classifier_node(state)  # type: ignore[arg-type]

    assert result == {"task_type": "simple_utility"}
    assert captured_model == ["openai/gpt-4o-mini"]


@pytest.mark.asyncio
async def test_classifier_node_uses_last_user_message():
    """Classifier picks the last user message from conversation history."""
    captured_messages: list[list[dict[str, Any]]] = []

    class FakeLLMResponse:
        content = '{"task_type": "execution", "confidence": 0.9}'
        tool_calls: list = []

    async def fake_invoke_llm(model: str, messages: list, **kwargs: Any) -> FakeLLMResponse:
        captured_messages.append(messages)
        return FakeLLMResponse()

    state: dict[str, Any] = {
        "messages": [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Latest user message"},
        ],
        "model_config": {"classifier": "openai/gpt-4o-mini"},
    }

    with patch("noa.orchestrator.nodes.classifier.invoke_llm", side_effect=fake_invoke_llm):
        await classifier_node(state)  # type: ignore[arg-type]

    assert len(captured_messages) == 1
    prompt_content = captured_messages[0][0]["content"]
    assert "Latest user message" in prompt_content
    assert "First message" not in prompt_content


# ---------------------------------------------------------------------------
# ModelConfig classifier field tests
# ---------------------------------------------------------------------------


def test_model_config_has_classifier_field():
    from noa.orchestrator.model_config import ModelConfig
    mc = ModelConfig()
    assert hasattr(mc, "classifier")
    assert mc.classifier != "none"


def test_model_config_to_dict_includes_classifier():
    from noa.orchestrator.model_config import ModelConfig
    mc = ModelConfig()
    d = mc.to_dict()
    assert "classifier" in d


def test_model_config_for_privacy_mode_external_uses_cheap_model():
    from noa.orchestrator.model_config import ModelConfig
    mc = ModelConfig.for_privacy_mode("external")
    assert mc.classifier == "openai/gpt-4o-mini"


def test_model_config_for_privacy_mode_private_uses_private_model():
    from noa.orchestrator.model_config import ModelConfig
    mc = ModelConfig.for_privacy_mode("private")
    # Private mode uses the private (Ollama) model for classifier
    assert mc.classifier != "openai/gpt-4o-mini"
    assert mc.classifier != "none"
