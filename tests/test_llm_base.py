from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from src.llm.base import (
    LLMClient,
    LLMResponse,
    OPENROUTER_CACHE_BREAKPOINT,
    _mark_cache_breakpoint,
    cache_tokens_from_langchain_usage,
    cost_from_langchain_response,
)


def test_llm_response_defaults():
    r = LLMResponse(
        content="hi", model="m", prompt_tokens=1, completion_tokens=1,
        total_tokens=2, latency_ms=1.0,
    )
    assert r.json_mode_used is False
    assert r.cache_read_tokens == 0
    assert r.cache_write_tokens == 0
    assert r.cost is None


def test_openrouter_cache_breakpoint_literal_is_stable():
    assert OPENROUTER_CACHE_BREAKPOINT == {"mode": "explicit"}


# ── cache_tokens_from_langchain_usage ────────────────────────────────────────

def test_cache_tokens_from_langchain_usage_present():
    response = SimpleNamespace(usage_metadata={
        "input_token_details": {"cache_read": 100, "cache_creation": 20},
    })
    assert cache_tokens_from_langchain_usage(response) == (100, 20)


def test_cache_tokens_from_langchain_usage_missing_usage_metadata_returns_zeros():
    assert cache_tokens_from_langchain_usage(SimpleNamespace()) == (0, 0)


def test_cache_tokens_from_langchain_usage_missing_details_returns_zeros():
    response = SimpleNamespace(usage_metadata={})
    assert cache_tokens_from_langchain_usage(response) == (0, 0)


def test_cache_tokens_from_langchain_usage_partial_fields_default_to_zero():
    response = SimpleNamespace(usage_metadata={"input_token_details": {"cache_read": None}})
    assert cache_tokens_from_langchain_usage(response) == (0, 0)


# ── cost_from_langchain_response ─────────────────────────────────────────────

def test_cost_from_langchain_response_present():
    response = SimpleNamespace(response_metadata={"token_usage": {"cost": 0.0042}})
    assert cost_from_langchain_response(response) == 0.0042


def test_cost_from_langchain_response_absent_returns_none_not_zero():
    response = SimpleNamespace(response_metadata={"token_usage": {}})
    assert cost_from_langchain_response(response) is None


def test_cost_from_langchain_response_missing_response_metadata_returns_none():
    assert cost_from_langchain_response(SimpleNamespace()) is None


# ── _mark_cache_breakpoint ────────────────────────────────────────────────────

def test_mark_cache_breakpoint_promotes_plain_string_to_marked_block():
    result = _mark_cache_breakpoint("hello")
    assert result == [{
        "type": "text", "text": "hello",
        "prompt_cache_breakpoint": {"mode": "explicit"},
    }]


def test_mark_cache_breakpoint_empty_string_is_noop():
    assert _mark_cache_breakpoint("") == ""


def test_mark_cache_breakpoint_marks_last_text_block_in_list():
    content = [{"type": "text", "text": "first"}, {"type": "text", "text": "second"}]
    result = _mark_cache_breakpoint(content)
    assert result[0] == {"type": "text", "text": "first"}  # untouched
    assert result[1]["prompt_cache_breakpoint"] == {"mode": "explicit"}


def test_mark_cache_breakpoint_returns_same_object_when_nothing_eligible():
    content = [{"type": "image_url", "url": "x"}]
    assert _mark_cache_breakpoint(content) is content


def test_mark_cache_breakpoint_empty_list_is_noop():
    content = []
    assert _mark_cache_breakpoint(content) is content


# ── LLMClient.complete_structured default implementation ────────────────────

class _Schema(BaseModel):
    smell_id: str
    confirmed: bool


class _FakeClient(LLMClient):
    """Minimal concrete LLMClient exercising only the base class's default
    complete_structured() (text-parse fallback), never a network call."""

    def __init__(self, raw_text: str):
        self._raw_text = raw_text

    def complete(self, prompt, system=None, timeout=None):
        return LLMResponse(
            content=self._raw_text, model="fake", prompt_tokens=1,
            completion_tokens=1, total_tokens=2, latency_ms=0.5,
        )


def test_complete_structured_default_parses_text_response_into_schema():
    client = _FakeClient('{"smell_id": "x", "confirmed": true}')
    parsed, response = client.complete_structured("prompt", schema=_Schema)
    assert parsed == _Schema(smell_id="x", confirmed=True)
    assert response.content == '{"smell_id": "x", "confirmed": true}'


def test_complete_structured_default_strips_markdown_fence():
    client = _FakeClient('```json\n{"smell_id": "y", "confirmed": false}\n```')
    parsed, _ = client.complete_structured("prompt", schema=_Schema)
    assert parsed.smell_id == "y"
    assert parsed.confirmed is False


def test_complete_structured_default_raises_on_invalid_json():
    client = _FakeClient("not json")
    with pytest.raises(Exception):
        client.complete_structured("prompt", schema=_Schema)
