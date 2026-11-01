from pathlib import Path

import pytest

import main


# ── _collect_files ────────────────────────────────────────────────────────────

def test_collect_files_single_file_mode_returns_that_file(tmp_path):
    f = tmp_path / "core.clj"
    f.write_text("(ns core)", encoding="utf-8")
    assert main._collect_files(f, is_dir=False) == [f]


def test_collect_files_single_file_wrong_extension_still_returned(tmp_path, caplog):
    f = tmp_path / "notes.txt"
    f.write_text("not clojure", encoding="utf-8")
    assert main._collect_files(f, is_dir=False) == [f]


def test_collect_files_dir_mode_finds_all_clojure_extensions_recursively(tmp_path):
    (tmp_path / "a.clj").write_text("", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.cljs").write_text("", encoding="utf-8")
    (tmp_path / "sub" / "c.cljc").write_text("", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("", encoding="utf-8")

    files = main._collect_files(tmp_path, is_dir=True)

    assert sorted(f.name for f in files) == ["a.clj", "b.cljs", "c.cljc"]


def test_collect_files_dir_mode_exits_when_nothing_found(tmp_path):
    (tmp_path / "ignored.txt").write_text("", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        main._collect_files(tmp_path, is_dir=True)
    assert excinfo.value.code == 1


# ── _api_key_for ──────────────────────────────────────────────────────────────

def test_api_key_for_known_providers(monkeypatch):
    monkeypatch.setattr(main.config, "openai_api_key", "openai-key")
    monkeypatch.setattr(main.config, "anthropic_api_key", "anthropic-key")
    monkeypatch.setattr(main.config, "google_api_key", "google-key")
    monkeypatch.setattr(main.config, "openrouter_api_key", "openrouter-key")

    assert main._api_key_for("openai") == "openai-key"
    assert main._api_key_for("anthropic") == "anthropic-key"
    assert main._api_key_for("gemini") == "google-key"
    assert main._api_key_for("openrouter") == "openrouter-key"
    assert main._api_key_for("ollama") == ""


def test_api_key_for_unknown_provider_returns_empty_string():
    assert main._api_key_for("does-not-exist") == ""


# ── _build_llm ────────────────────────────────────────────────────────────────

def test_build_llm_raises_for_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        main._build_llm("does-not-exist", "some-model")


def test_build_llm_dispatches_to_langchain_client(monkeypatch):
    captured = {}

    class _FakeLangChainLLMClient:
        def __init__(self, provider, model, api_key, use_prompt_cache):
            captured.update(provider=provider, model=model, api_key=api_key, use_prompt_cache=use_prompt_cache)

    monkeypatch.setattr("src.llm.langchain_client.LangChainLLMClient", _FakeLangChainLLMClient)
    monkeypatch.setattr(main.config, "openai_api_key", "sk-x")

    result = main._build_llm("openai", "gpt-4o")
    assert isinstance(result, _FakeLangChainLLMClient)
    assert captured == {"provider": "openai", "model": "gpt-4o", "api_key": "sk-x", "use_prompt_cache": False}


def test_build_llm_passes_use_prompt_cache_through(monkeypatch):
    captured = {}

    class _FakeLangChainLLMClient:
        def __init__(self, provider, model, api_key, use_prompt_cache):
            captured["use_prompt_cache"] = use_prompt_cache

    monkeypatch.setattr("src.llm.langchain_client.LangChainLLMClient", _FakeLangChainLLMClient)
    main._build_llm("openrouter", "google/gemini-2.0-flash-001", use_prompt_cache=True)
    assert captured["use_prompt_cache"] is True


def test_build_llm_resolves_api_key_per_provider(monkeypatch):
    captured = {}

    class _FakeLangChainLLMClient:
        def __init__(self, provider, model, api_key, use_prompt_cache):
            captured["api_key"] = api_key

    monkeypatch.setattr("src.llm.langchain_client.LangChainLLMClient", _FakeLangChainLLMClient)
    monkeypatch.setattr(main.config, "anthropic_api_key", "sk-anthropic")
    main._build_llm("anthropic", "claude-x")
    assert captured["api_key"] == "sk-anthropic"


# ── _build_vectordb ───────────────────────────────────────────────────────────

def test_build_vectordb_raises_for_unknown_provider():
    with pytest.raises(ValueError, match="Unknown VectorDB provider"):
        main._build_vectordb("does-not-exist")


def test_build_vectordb_dispatches_mock(monkeypatch):
    class _FakeMockClient:
        pass

    monkeypatch.setattr("src.vectordb.mock_client.MockVectorDBClient", _FakeMockClient)
    assert isinstance(main._build_vectordb("mock"), _FakeMockClient)


def test_build_vectordb_dispatches_chroma(monkeypatch):
    captured = {}

    class _FakeChromaClient:
        def __init__(self, persist_path, google_api_key):
            captured.update(persist_path=persist_path, google_api_key=google_api_key)

    monkeypatch.setattr("src.vectordb.chroma_client.ChromaVectorDBClient", _FakeChromaClient)
    monkeypatch.setattr(main.config, "chromadb_persist_path", "/tmp/chroma")
    monkeypatch.setattr(main.config, "google_api_key", "g-key")

    result = main._build_vectordb("chroma")
    assert isinstance(result, _FakeChromaClient)
    assert captured == {"persist_path": "/tmp/chroma", "google_api_key": "g-key"}
