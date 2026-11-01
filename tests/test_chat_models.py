"""Tests for build_chat_model()'s provider dispatch (D24) — never touches the
network; each branch's LangChain chat model class is monkeypatched at its
source module before the call, so the SDK client is never actually
constructed for real."""

import pytest

from src.llm.chat_models import build_chat_model


def test_build_chat_model_raises_for_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        build_chat_model("does-not-exist", "some-model", "key")


def test_build_chat_model_dispatches_gemini(monkeypatch):
    captured = {}

    class _FakeChatGoogleGenerativeAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "langchain_google_genai.ChatGoogleGenerativeAI", _FakeChatGoogleGenerativeAI
    )
    result = build_chat_model("gemini", "gemini-flash-latest", "fake-key")
    assert isinstance(result, _FakeChatGoogleGenerativeAI)
    assert captured == {"model": "gemini-flash-latest", "google_api_key": "fake-key", "temperature": 0}


def test_build_chat_model_dispatches_openai(monkeypatch):
    captured = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeChatOpenAI)
    result = build_chat_model("openai", "gpt-4o", "sk-x")
    assert isinstance(result, _FakeChatOpenAI)
    assert captured == {"model": "gpt-4o", "api_key": "sk-x", "temperature": 0}


def test_build_chat_model_dispatches_anthropic_with_max_tokens_and_no_temperature(monkeypatch):
    captured = {}

    class _FakeChatAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("langchain_anthropic.ChatAnthropic", _FakeChatAnthropic)
    result = build_chat_model("anthropic", "claude-x", "sk-x")
    assert isinstance(result, _FakeChatAnthropic)
    assert captured == {"model": "claude-x", "api_key": "sk-x", "max_tokens": 8192}
    assert "temperature" not in captured


def test_build_chat_model_dispatches_openrouter(monkeypatch):
    captured = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeChatOpenAI)
    result = build_chat_model("openrouter", "google/gemini-2.0-flash-001", "sk-x")
    assert isinstance(result, _FakeChatOpenAI)
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["api_key"] == "sk-x"


def test_build_chat_model_dispatches_ollama_without_api_key(monkeypatch):
    captured = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeChatOpenAI)
    result = build_chat_model("ollama", "llama3.1", None)
    assert isinstance(result, _FakeChatOpenAI)
    assert captured["base_url"] == "http://localhost:11434/v1"
    assert captured["api_key"] == "ollama"  # ignores the passed-in key
