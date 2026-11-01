"""Tests for LangChainLLMClient — this codebase's single LLMClient
implementation (D24), built on top of a real LangChain chat model per
provider. Constructing the chat model does no I/O (confirmed by these tests
running with a fake API key and no network access); what's monkeypatched is
always the bound `.invoke()`/`.with_structured_output()` method on the
model's own class (these are pydantic models — they reject setting
arbitrary attributes on an instance, so the class is patched instead), never
the network call itself."""

from types import SimpleNamespace

import pytest

from src.artifact.schema import DetectionOutput
from src.llm.langchain_client import LangChainLLMClient


def _client(provider="gemini", model="m", use_prompt_cache=False):
    return LangChainLLMClient(provider=provider, model=model, api_key="fake-key", use_prompt_cache=use_prompt_cache)


# ── complete() ────────────────────────────────────────────────────────────────

def test_complete_normalizes_usage_and_content(monkeypatch):
    client = _client()
    fake_response = SimpleNamespace(
        content="hello world",
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        response_metadata={},
    )
    monkeypatch.setattr(type(client._llm), "invoke", lambda self, messages, **kw: fake_response)

    result = client.complete("say hi", system="be nice")

    assert result.content == "hello world"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.total_tokens == 15
    assert result.model == "m"  # falls back to configured name — no model_name/model in response_metadata


def test_complete_joins_list_content():
    client = _client()
    joined = client._normalize_content([{"type": "text", "text": "part one "}, {"type": "text", "text": "part two"}])
    assert joined == "part one part two"


def test_complete_defaults_none_content_to_empty_string(monkeypatch):
    client = _client()
    fake_response = SimpleNamespace(content=None, usage_metadata=None, response_metadata={})
    monkeypatch.setattr(type(client._llm), "invoke", lambda self, messages, **kw: fake_response)

    result = client.complete("x")
    assert result.content == ""
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0


def test_complete_resolves_model_name_from_response_metadata(monkeypatch):
    client = _client(model="claude-x")
    fake_response = SimpleNamespace(
        content="ok", usage_metadata={"input_tokens": 1, "output_tokens": 1},
        response_metadata={"model_name": "claude-x-20260101"},
    )
    monkeypatch.setattr(type(client._llm), "invoke", lambda self, messages, **kw: fake_response)

    result = client.complete("prompt")
    assert result.model == "claude-x-20260101"


def test_complete_reports_cache_tokens_and_cost_when_present(monkeypatch):
    client = _client(provider="openrouter")
    fake_response = SimpleNamespace(
        content="answer",
        usage_metadata={
            "input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
            "input_token_details": {"cache_read": 80, "cache_creation": 0},
        },
        response_metadata={"token_usage": {"cost": 0.0012}},
    )
    monkeypatch.setattr(type(client._llm), "invoke", lambda self, messages, **kw: fake_response)

    result = client.complete("prompt", system="sys")
    assert result.cache_read_tokens == 80
    assert result.cost == 0.0012


# ── OpenRouter system-message cache breakpoint (D17) ─────────────────────────

def test_build_messages_plain_system_when_cache_disabled():
    client = _client(provider="openrouter", use_prompt_cache=False)
    messages = client._build_messages("prompt", "sys prompt")
    assert messages[0].content == "sys prompt"


def test_build_messages_marks_breakpoint_when_cache_enabled_on_openrouter():
    client = _client(provider="openrouter", use_prompt_cache=True)
    messages = client._build_messages("prompt", "sys prompt")
    assert messages[0].content == [{
        "type": "text", "text": "sys prompt",
        "prompt_cache_breakpoint": {"mode": "explicit"},
    }]


def test_build_messages_use_prompt_cache_is_noop_for_non_openrouter_providers():
    client = _client(provider="gemini", use_prompt_cache=True)
    messages = client._build_messages("prompt", "sys prompt")
    assert messages[0].content == "sys prompt"


# ── complete_structured() ─────────────────────────────────────────────────────

class _FakeStructuredLLM:
    def __init__(self, result):
        self._result = result

    def invoke(self, messages, **kw):
        return self._result


def test_complete_structured_uses_with_structured_output(monkeypatch):
    client = _client()
    parsed_obj = DetectionOutput(candidates=[{"smell_id": "a"}])
    raw_ai_message = SimpleNamespace(
        content='{"candidates": [{"smell_id": "a"}]}',
        usage_metadata={"input_tokens": 2, "output_tokens": 2},
        response_metadata={},
    )
    monkeypatch.setattr(
        type(client._llm), "with_structured_output",
        lambda self, *a, **k: _FakeStructuredLLM({"raw": raw_ai_message, "parsed": parsed_obj}),
    )

    parsed, response = client.complete_structured("x", schema=DetectionOutput)
    assert parsed is parsed_obj
    assert response.json_mode_used is True


def test_complete_structured_reconstructs_empty_text_content(monkeypatch):
    client = _client()
    parsed_obj = DetectionOutput(candidates=[{"smell_id": "a"}])
    raw_ai_message = SimpleNamespace(
        content="",  # tool-call style response -> empty text content
        usage_metadata={"input_tokens": 3, "output_tokens": 1},
        response_metadata={},
    )
    monkeypatch.setattr(
        type(client._llm), "with_structured_output",
        lambda self, *a, **k: _FakeStructuredLLM({"raw": raw_ai_message, "parsed": parsed_obj}),
    )

    parsed, response = client.complete_structured("x", schema=DetectionOutput)
    assert parsed is parsed_obj
    assert '"smell_id": "a"' in response.content  # reconstructed from parsed


def test_complete_structured_falls_back_to_text_parsing_on_error(monkeypatch):
    client = _client()

    def raise_error(self, *a, **k):
        raise RuntimeError("model does not support structured output")

    monkeypatch.setattr(type(client._llm), "with_structured_output", raise_error)
    fallback_response = SimpleNamespace(
        content='{"candidates": []}', usage_metadata={"input_tokens": 1, "output_tokens": 1},
        response_metadata={},
    )
    monkeypatch.setattr(type(client._llm), "invoke", lambda self, messages, **kw: fallback_response)

    parsed, response = client.complete_structured("x", schema=DetectionOutput)
    assert parsed.candidates == []
    assert response.json_mode_used is False  # went through the base class's text-parse fallback


def test_complete_structured_falls_back_when_parsed_is_none(monkeypatch):
    client = _client()
    raw_ai_message = SimpleNamespace(content="", usage_metadata=None, response_metadata={})
    monkeypatch.setattr(
        type(client._llm), "with_structured_output",
        lambda self, *a, **k: _FakeStructuredLLM({"raw": raw_ai_message, "parsed": None}),
    )
    fallback_response = SimpleNamespace(
        content='{"candidates": []}', usage_metadata={"input_tokens": 1, "output_tokens": 1},
        response_metadata={},
    )
    monkeypatch.setattr(type(client._llm), "invoke", lambda self, messages, **kw: fallback_response)

    parsed, response = client.complete_structured("x", schema=DetectionOutput)
    assert parsed.candidates == []
