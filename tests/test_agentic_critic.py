from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agents.agentic_critic import (
    AgenticCriticAgent,
    _find_function_file,
    _mark_cache_breakpoint,
)
from src.artifact.schema import CandidateSmell
from src.tools.example_lookup import ExampleStore


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


# ── _find_function_file ──────────────────────────────────────────────────────

def test_find_function_file_checks_current_file_first(tmp_path):
    current = tmp_path / "current.clj"
    current.write_text("(defn helper [] 1)", encoding="utf-8")
    other = tmp_path / "sub" / "other.clj"
    other.parent.mkdir()
    other.write_text("(defn helper [] 2)", encoding="utf-8")

    found = _find_function_file("helper", current_file=current, search_root=tmp_path)
    assert found == current


def test_find_function_file_falls_back_to_search_root(tmp_path):
    current = tmp_path / "current.clj"
    current.write_text("(ns current)", encoding="utf-8")
    other = tmp_path / "sub" / "other.clj"
    other.parent.mkdir()
    other.write_text("(defn helper [] 2)", encoding="utf-8")

    found = _find_function_file("helper", current_file=current, search_root=tmp_path)
    assert found == other


def test_find_function_file_returns_none_when_not_found(tmp_path):
    current = tmp_path / "current.clj"
    current.write_text("(ns current)", encoding="utf-8")
    assert _find_function_file("nope", current_file=current, search_root=tmp_path) is None


def test_find_function_file_matches_defn_defmacro_and_def_variants(tmp_path):
    f = tmp_path / "f.clj"
    f.write_text("(defmacro my-macro [] 1)", encoding="utf-8")
    assert _find_function_file("my-macro", current_file=f, search_root=None) == f


# ── AgenticCriticAgent construction (network mocked out) ────────────────────

class _FakeChatModel:
    """Stand-in for a LangChain BaseChatModel — never makes a network call."""

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self


@pytest.fixture
def agent(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.agents.agentic_critic.build_chat_model",
        lambda provider, model, api_key: _FakeChatModel(),
    )
    store = ExampleStore(dataset_path=str(tmp_path / "no-such-dataset"))
    return AgenticCriticAgent(provider="gemini", model="gemini-flash-latest", example_store=store)


def test_agent_construction_wires_four_tools_bound_to_model(agent):
    tool_names = {t.name for t in agent.tools}
    assert tool_names == {
        "get_smell_examples", "list_doc_sections", "get_doc_section", "get_function_source",
    }
    assert agent.llm_with_tools.bound_tools == agent.tools


def test_reset_run_derives_session_id_from_run_id_regardless_of_provider(monkeypatch, tmp_path):
    """reset_run() itself doesn't gate on provider — it always derives
    session_id when a run_id is given. The openrouter-only behavior lives
    in invoke_kwargs() (see its own tests below), which is where it
    actually matters (only openrouter's `extra_body` reads it)."""
    monkeypatch.setattr(
        "src.agents.agentic_critic.build_chat_model",
        lambda provider, model, api_key: _FakeChatModel(),
    )
    store = ExampleStore(dataset_path=str(tmp_path))
    gemini_agent = AgenticCriticAgent(provider="gemini", model="m", example_store=store)
    gemini_agent.reset_run(file_path="f.clj", search_root=None, run_id="run-1")
    assert gemini_agent.session_id == "critic-agent-run-1"

    or_agent = AgenticCriticAgent(provider="openrouter", model="m", example_store=store)
    or_agent.reset_run(file_path="f.clj", search_root=None, run_id="run-1")
    assert or_agent.session_id == "critic-agent-run-1"


def test_reset_run_session_id_none_when_no_run_id_given(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.agents.agentic_critic.build_chat_model",
        lambda provider, model, api_key: _FakeChatModel(),
    )
    store = ExampleStore(dataset_path=str(tmp_path))
    agent = AgenticCriticAgent(provider="openrouter", model="m", example_store=store)
    agent.reset_run(file_path="f.clj", search_root=None)
    assert agent.session_id is None


def test_reset_run_resets_per_file_counters_and_dedup_state(agent):
    agent._tool_calls = 5
    agent._examples_sent = {"a": {"id1"}}
    agent._doc_index_sent = True
    agent.cache_read_tokens = 10

    agent.reset_run(file_path="f.clj", search_root=None)

    assert agent._tool_calls == 0
    assert agent._examples_sent == {}
    assert agent._doc_index_sent is False
    assert agent.cache_read_tokens == 0


# ── get_smell_examples tool ───────────────────────────────────────────────────

def _make_agent_with_dataset(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.agents.agentic_critic.build_chat_model",
        lambda provider, model, api_key: _FakeChatModel(),
    )
    root = tmp_path / "dataset"
    smell_dir = root / "smells" / "cat" / "nested_atoms"
    smell_dir.mkdir(parents=True)
    (smell_dir / "example_bad_1.md").write_text(
        "```clojure\n(atom (atom 1))\n```", encoding="utf-8"
    )
    (smell_dir / "example_good_1.md").write_text(
        "```clojure\n(atom {:x 1})\n```", encoding="utf-8"
    )
    docs_dir = root / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("## Section One [#s1]\nBody text.\n", encoding="utf-8")

    store = ExampleStore(dataset_path=str(root))
    return AgenticCriticAgent(provider="gemini", model="m", example_store=store)


def _tool(agent, name):
    return next(t for t in agent.tools if t.name == name)


def test_get_smell_examples_rejects_empty_list(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    result = _tool(agent, "get_smell_examples").invoke({"smell_ids": []})
    assert "No smell_ids provided" in result


def test_get_smell_examples_returns_progress_note_and_tracks_sent_ids(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    tool = _tool(agent, "get_smell_examples")

    result = tool.invoke({"smell_ids": ["nested_atoms"]})
    assert "[nested_atoms]" in result
    assert "more available" in result or "that's all of them" in result
    assert agent._tool_calls == 1
    assert agent._examples_sent["nested_atoms"]  # ids recorded


def test_get_smell_examples_second_call_reports_no_more_when_exhausted(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    tool = _tool(agent, "get_smell_examples")
    tool.invoke({"smell_ids": ["nested_atoms"]})
    second = tool.invoke({"smell_ids": ["nested_atoms"]})
    assert "No more examples" in second


def test_get_smell_examples_unknown_smell_id_reports_no_examples(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    tool = _tool(agent, "get_smell_examples")
    result = tool.invoke({"smell_ids": ["never_heard_of_this"]})
    assert "No examples found" in result


# ── list_doc_sections / get_doc_section tools ────────────────────────────────

def test_list_doc_sections_only_sent_once_per_run(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    tool = _tool(agent, "list_doc_sections")

    first = tool.invoke({})
    assert "Section One" in first

    second = tool.invoke({})
    assert "already fetched" in second


def test_get_doc_section_rejects_empty_sections_list(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    tool = _tool(agent, "get_doc_section")
    result = tool.invoke({"doc": "guide.md", "sections": []})
    assert "No sections provided" in result


def test_get_doc_section_returns_section_body(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    tool = _tool(agent, "get_doc_section")
    result = tool.invoke({"doc": "guide.md", "sections": ["s1"]})
    assert "Body text." in result


# ── get_function_source tool ─────────────────────────────────────────────────

def test_get_function_source_rejects_empty_list(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    tool = _tool(agent, "get_function_source")
    result = tool.invoke({"function_names": []})
    assert "No function_names provided" in result


def test_get_function_source_without_current_file_reports_unavailable(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    tool = _tool(agent, "get_function_source")
    result = tool.invoke({"function_names": ["helper"]})
    assert "No source file available" in result


def test_get_function_source_reports_already_visible_when_file_shown_in_full(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    current_file = tmp_path / "current.clj"
    current_file.write_text("(defn helper [] 1)", encoding="utf-8")
    agent.reset_run(file_path=str(current_file), search_root=None)
    agent._file_shown_in_full = True

    tool = _tool(agent, "get_function_source")
    result = tool.invoke({"function_names": ["helper"]})
    assert "Already visible" in result


def test_get_function_source_reports_not_found_for_unknown_function(monkeypatch, tmp_path):
    agent = _make_agent_with_dataset(monkeypatch, tmp_path)
    current_file = tmp_path / "current.clj"
    current_file.write_text("(ns current)", encoding="utf-8")
    agent.reset_run(file_path=str(current_file), search_root=None)

    tool = _tool(agent, "get_function_source")
    result = tool.invoke({"function_names": ["totally-unknown-fn"]})
    assert "Not found anywhere in the project" in result


# ── build_initial_messages ────────────────────────────────────────────────────

CATALOG = {"nested_atoms": {"id": "nested_atoms", "name": "Nested Atoms", "summary": "atom in atom"}}


def test_build_initial_messages_default_provider_plain_messages(agent):
    candidates = [CandidateSmell(smell_id="nested_atoms", element_name="f", snippet="(atom (atom 1))")]
    contexts = {"nested_atoms::f": "(atom (atom 1))"}

    messages, user_prompt = agent.build_initial_messages(contexts, candidates, CATALOG)

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[0].content, str)
    assert isinstance(messages[1], HumanMessage)
    assert "Nested Atoms" in user_prompt
    assert "(atom (atom 1))" in user_prompt


def test_build_initial_messages_dedupes_catalog_entries_by_smell_id(agent):
    candidates = [
        CandidateSmell(smell_id="nested_atoms", element_name="f1"),
        CandidateSmell(smell_id="nested_atoms", element_name="f2"),
    ]
    contexts = {"nested_atoms::f1": "code1", "nested_atoms::f2": "code2"}
    _, user_prompt = agent.build_initial_messages(contexts, candidates, CATALOG)
    assert user_prompt.count("**nested_atoms**") == 1


def test_build_initial_messages_anthropic_marks_cache_control(agent):
    agent.provider = "anthropic"
    candidates = [CandidateSmell(smell_id="nested_atoms", element_name="f")]
    contexts = {"nested_atoms::f": "code"}

    messages, _ = agent.build_initial_messages(contexts, candidates, CATALOG)

    assert messages[0].content[0]["cache_control"] == {"type": "ephemeral"}
    assert messages[1].content[0]["cache_control"] == {"type": "ephemeral"}


def test_build_initial_messages_openrouter_marks_prompt_cache_breakpoint(agent):
    agent.provider = "openrouter"
    candidates = [CandidateSmell(smell_id="nested_atoms", element_name="f")]
    contexts = {"nested_atoms::f": "code"}

    messages, _ = agent.build_initial_messages(contexts, candidates, CATALOG)

    assert messages[0].content[0]["prompt_cache_breakpoint"] == {"mode": "explicit"}
    assert messages[1].content[0]["prompt_cache_breakpoint"] == {"mode": "explicit"}


def test_build_initial_messages_file_scope_embeds_full_file_once(agent):
    candidates = [
        CandidateSmell(smell_id="ns_smell", element_name="my.ns", snippet="(ns my.ns)\n(defn f [] 1)"),
        CandidateSmell(smell_id="fn_smell", element_name="f"),
    ]
    contexts = {"ns_smell::my.ns": "__FILE_SCOPE__", "fn_smell::f": "should not appear"}

    _, user_prompt = agent.build_initial_messages(contexts, candidates, {})

    assert "All Candidates (full file provided" in user_prompt
    assert "should not appear" not in user_prompt
    assert agent._file_shown_in_full is True


# ── with_cache_breakpoint ─────────────────────────────────────────────────────

def test_with_cache_breakpoint_noop_for_non_openrouter(agent):
    agent.provider = "gemini"
    messages = [HumanMessage(content="hi")]
    assert agent.with_cache_breakpoint(messages) is messages


def test_with_cache_breakpoint_noop_for_empty_messages(agent):
    agent.provider = "openrouter"
    assert agent.with_cache_breakpoint([]) == []


def test_with_cache_breakpoint_marks_last_message_only_for_openrouter(agent):
    agent.provider = "openrouter"
    first = HumanMessage(content="first")
    last = HumanMessage(content="last")
    result = agent.with_cache_breakpoint([first, last])

    assert result[0] is first  # untouched
    assert result[1] is not last  # new object, original left alone
    assert result[1].content[0]["prompt_cache_breakpoint"] == {"mode": "explicit"}
    assert last.content == "last"  # original untouched


# ── invoke_kwargs ──────────────────────────────────────────────────────────────

def test_invoke_kwargs_empty_for_non_openrouter(agent):
    agent.provider = "gemini"
    assert agent.invoke_kwargs() == {}


def test_invoke_kwargs_carries_session_id_for_openrouter(agent):
    agent.provider = "openrouter"
    agent.session_id = "critic-agent-xyz"
    assert agent.invoke_kwargs() == {"extra_body": {"session_id": "critic-agent-xyz"}}


def test_invoke_kwargs_empty_when_openrouter_but_no_session_id(agent):
    agent.provider = "openrouter"
    agent.session_id = None
    assert agent.invoke_kwargs() == {}


# ── record_cache_usage / record_cost ─────────────────────────────────────────

def test_record_cache_usage_accumulates_across_calls(agent):
    r1 = SimpleNamespace(usage_metadata={"input_token_details": {"cache_read": 10, "cache_creation": 2}})
    r2 = SimpleNamespace(usage_metadata={"input_token_details": {"cache_read": 5, "cache_creation": 0}})
    agent.record_cache_usage(r1)
    agent.record_cache_usage(r2)
    assert agent.cache_read_tokens == 15
    assert agent.cache_write_tokens == 2


def test_record_cache_usage_handles_missing_usage_metadata(agent):
    agent.record_cache_usage(SimpleNamespace())
    assert agent.cache_read_tokens == 0
    assert agent.cache_write_tokens == 0


def test_record_cost_accumulates_and_leaves_none_when_never_reported(agent):
    assert agent.cost is None
    agent.record_cost(SimpleNamespace(response_metadata={"token_usage": {"cost": 0.01}}))
    assert agent.cost == 0.01
    agent.record_cost(SimpleNamespace(response_metadata={"token_usage": {"cost": 0.02}}))
    assert agent.cost == pytest.approx(0.03)


def test_record_cost_noop_when_not_reported(agent):
    agent.record_cost(SimpleNamespace(response_metadata={}))
    assert agent.cost is None


# ── extract_final_text / token_usage / build_transcript ─────────────────────

def test_extract_final_text_returns_last_ai_message_string_content():
    messages = [
        SystemMessage(content="sys"),
        HumanMessage(content="hi"),
        AIMessage(content="first answer"),
        ToolMessage(content="tool result", tool_call_id="1"),
        AIMessage(content="final answer"),
    ]
    assert AgenticCriticAgent.extract_final_text(messages) == "final answer"


def test_extract_final_text_joins_list_content_blocks():
    messages = [AIMessage(content=[{"type": "text", "text": "part1 "}, {"type": "text", "text": "part2"}])]
    assert AgenticCriticAgent.extract_final_text(messages) == "part1 part2"


def test_token_usage_sums_across_all_ai_message_turns():
    messages = [
        AIMessage(content="a", usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}),
        ToolMessage(content="x", tool_call_id="1"),
        AIMessage(content="b", usage_metadata={"input_tokens": 20, "output_tokens": 8, "total_tokens": 28}),
    ]
    prompt, completion = AgenticCriticAgent.token_usage(messages)
    assert prompt == 30
    assert completion == 13


def test_build_transcript_records_tool_calls_and_results_skipping_first_two_messages():
    messages = [
        SystemMessage(content="sys"),
        HumanMessage(content="initial"),
        AIMessage(content="", tool_calls=[{"name": "get_smell_examples", "args": {"smell_ids": ["a"]}, "id": "1"}]),
        ToolMessage(content="evidence text", tool_call_id="1", name="get_smell_examples"),
        AIMessage(content="final verdict json"),
    ]
    transcript = AgenticCriticAgent.build_transcript(messages)
    assert "AI called tool: get_smell_examples({'smell_ids': ['a']})" in transcript
    assert "[Tool result — get_smell_examples]\nevidence text" in transcript
    assert "final verdict json" in transcript
    assert "initial" not in transcript  # first two messages skipped
