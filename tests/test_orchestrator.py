from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.agentic_critic import AgenticCriticAgent
from src.artifact.schema import CandidateSmell, Verdict
from src.llm.base import LLMResponse
from src.orchestrator.orchestrator import SMELL_SCOPE, Orchestrator
from src.orchestrator.retry import MaxRetriesExceeded
from src.tools.example_lookup import ExampleStore
from tests.conftest import FakeLLMClient


# ── Construction validation ───────────────────────────────────────────────────

class _StubDetector:
    def filter_catalog(self, code):
        return {}

    def run(self, code, timeout=None, catalog=None):
        raise NotImplementedError


class _StubCritic:
    tools = []


def test_orchestrator_rejects_unknown_mode():
    with pytest.raises(ValueError, match="Unknown orchestrator mode"):
        Orchestrator(detector=_StubDetector(), retriever=None, critic=_StubCritic(), mode="bogus")


def test_orchestrator_agentic_mode_requires_catalog():
    with pytest.raises(ValueError, match="requires the `catalog`"):
        Orchestrator(detector=_StubDetector(), retriever=None, critic=_StubCritic(), mode="agentic")


# ── SMELL_SCOPE / static routing ──────────────────────────────────────────────

def test_smell_scope_maps_namespace_level_smells():
    assert SMELL_SCOPE["single_segment_namespace"] == "ns_form"
    assert SMELL_SCOPE["namespace_load_side_effects"] == "file"
    assert "unnecessary_into" not in SMELL_SCOPE  # defaults to function-level


def test_route_after_detect_no_candidates():
    assert Orchestrator._route_after_detect({"no_candidates": True}) == "no_candidates"


def test_route_after_detect_has_candidates():
    assert Orchestrator._route_after_detect({"no_candidates": False}) == "extract"


def test_route_after_finalize_done_routes_to_end():
    from langgraph.graph import END
    assert Orchestrator._route_after_finalize({"agentic_judge_done": True}) == END


def test_route_after_finalize_not_done_routes_back_to_agent():
    assert Orchestrator._route_after_finalize({"agentic_judge_done": False}) == "agent"


# ── _node_extract (subprocess mocked) ────────────────────────────────────────

def _rag_orchestrator():
    return Orchestrator(detector=_StubDetector(), retriever=SimpleNamespace(), critic=SimpleNamespace(), mode="rag")


def test_node_extract_function_scope_success(monkeypatch):
    orch = _rag_orchestrator()
    monkeypatch.setattr(
        "src.orchestrator.orchestrator.subprocess.run",
        lambda args, **kw: SimpleNamespace(stdout="(defn f [] 1)\n", stderr=""),
    )
    candidates = [CandidateSmell(smell_id="unnecessary_into", element_name="f")]
    state = {"code": "(ns x)\n(defn f [] 1)", "file_path": "x.clj", "candidates": candidates}

    result = orch._node_extract(state)

    assert result["candidate_contexts"]["unnecessary_into::f"] == "(defn f [] 1)"
    assert candidates[0].snippet == "(defn f [] 1)"


def test_node_extract_file_scope_uses_full_code_without_subprocess(monkeypatch):
    orch = _rag_orchestrator()
    called = {"n": 0}
    monkeypatch.setattr(
        "src.orchestrator.orchestrator.subprocess.run",
        lambda *a, **kw: called.__setitem__("n", called["n"] + 1),
    )
    candidates = [CandidateSmell(smell_id="namespace_load_side_effects", element_name="my.ns")]
    state = {"code": "(ns my.ns)\n(println 1)", "file_path": "x.clj", "candidates": candidates}

    result = orch._node_extract(state)

    assert result["candidate_contexts"]["namespace_load_side_effects::my.ns"] == "__FILE_SCOPE__"
    assert candidates[0].snippet == "(ns my.ns)\n(println 1)"
    assert called["n"] == 0


def test_node_extract_missing_element_name_falls_back_to_full_code(monkeypatch):
    orch = _rag_orchestrator()
    monkeypatch.setattr(
        "src.orchestrator.orchestrator.subprocess.run",
        lambda *a, **kw: pytest.fail("subprocess should not be called"),
    )
    candidates = [CandidateSmell(smell_id="unnecessary_into", element_name=None)]
    state = {"code": "(defn f [] 1)", "file_path": "x.clj", "candidates": candidates}

    result = orch._node_extract(state)
    assert result["candidate_contexts"]["unnecessary_into::None"] == "(defn f [] 1)"


def test_node_extract_subprocess_error_falls_back_to_full_code(monkeypatch):
    import subprocess as sp
    orch = _rag_orchestrator()

    def _raise(*a, **kw):
        raise sp.CalledProcessError(1, "bb", output="", stderr="boom")
    monkeypatch.setattr("src.orchestrator.orchestrator.subprocess.run", _raise)

    candidates = [CandidateSmell(smell_id="unnecessary_into", element_name="f")]
    state = {"code": "(defn f [] 1)", "file_path": "x.clj", "candidates": candidates}

    result = orch._node_extract(state)
    assert result["candidate_contexts"]["unnecessary_into::f"] == "(defn f [] 1)"


def test_node_extract_babashka_not_found_falls_back_to_full_code(monkeypatch):
    orch = _rag_orchestrator()
    monkeypatch.setattr(
        "src.orchestrator.orchestrator.subprocess.run",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()),
    )
    candidates = [CandidateSmell(smell_id="unnecessary_into", element_name="f")]
    state = {"code": "(defn f [] 1)", "file_path": "x.clj", "candidates": candidates}

    result = orch._node_extract(state)
    assert result["candidate_contexts"]["unnecessary_into::f"] == "(defn f [] 1)"


def test_node_extract_empty_stdout_falls_back_with_warning(monkeypatch):
    orch = _rag_orchestrator()
    monkeypatch.setattr(
        "src.orchestrator.orchestrator.subprocess.run",
        lambda args, **kw: SimpleNamespace(stdout="   ", stderr=""),
    )
    candidates = [CandidateSmell(smell_id="unnecessary_into", element_name="f")]
    state = {"code": "(defn f [] 1)", "file_path": "x.clj", "candidates": candidates}

    result = orch._node_extract(state)
    assert result["candidate_contexts"]["unnecessary_into::f"] == "(defn f [] 1)"


# ── _node_no_candidates / _node_pre_filter ───────────────────────────────────

def test_node_no_candidates_returns_empty_dict():
    assert Orchestrator._node_no_candidates({}) == {}


def test_node_pre_filter_delegates_to_detector():
    class _Detector(_StubDetector):
        def filter_catalog(self, code):
            assert code == "the code"
            return {"a": {}}

    orch = Orchestrator(detector=_Detector(), retriever=SimpleNamespace(), critic=SimpleNamespace(), mode="rag")
    result = orch._node_pre_filter({"code": "the code"})
    assert result == {"filtered_catalog": {"a": {}}}


# ── _node_detect ──────────────────────────────────────────────────────────────

def test_node_detect_returns_candidates_and_metrics(monkeypatch):
    monkeypatch.setattr("src.orchestrator.retry.time.sleep", lambda s: None)

    candidates = [CandidateSmell(smell_id="a", element_name="f")]
    response = LLMResponse(content="{}", model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)

    class _Detector(_StubDetector):
        def run(self, code, timeout=None, catalog=None):
            return candidates, response, "prompt", "system"

    orch = Orchestrator(detector=_Detector(), retriever=SimpleNamespace(), critic=SimpleNamespace(), mode="rag")
    result = orch._node_detect({"code": "x", "filtered_catalog": {}})

    assert result["candidates"] == candidates
    assert result["no_candidates"] is False
    assert result["detection_retries"] == 0


def test_node_detect_no_candidates_flag_set_when_empty():
    response = LLMResponse(content="{}", model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)

    class _Detector(_StubDetector):
        def run(self, code, timeout=None, catalog=None):
            return [], response, "prompt", "system"

    orch = Orchestrator(detector=_Detector(), retriever=SimpleNamespace(), critic=SimpleNamespace(), mode="rag")
    result = orch._node_detect({"code": "x", "filtered_catalog": {}})
    assert result["no_candidates"] is True


def test_node_detect_raises_max_retries_exceeded_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("src.orchestrator.retry.time.sleep", lambda s: None)
    from src.artifact.validator import MalformedOutputError

    class _Detector(_StubDetector):
        def run(self, code, timeout=None, catalog=None):
            raise MalformedOutputError("always bad")

    orch = Orchestrator(
        detector=_Detector(), retriever=SimpleNamespace(), critic=SimpleNamespace(),
        mode="rag", max_retries=1,
    )
    with pytest.raises(MaxRetriesExceeded):
        orch._node_detect({"code": "x", "filtered_catalog": {}})


# ── _node_judge_rag ───────────────────────────────────────────────────────────

def test_node_judge_rag_combines_retriever_and_critic():
    from src.vectordb.base import ContextPackage

    candidates = [CandidateSmell(smell_id="a", element_name="f")]
    packages = [ContextPackage(smell_id="a")]
    verdicts = [Verdict(smell_id="a", element_name="f", confirmed=True, confidence="high", reasoning="r")]
    response = LLMResponse(content="{}", model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)

    class _Retriever:
        def run(self, candidates, top_k=3):
            return packages, 12.5

    class _Critic:
        def run(self, candidate_contexts, candidates, context_packages, timeout=None):
            assert context_packages == packages
            return verdicts, response, "prompt", "system"

    orch = Orchestrator(detector=_StubDetector(), retriever=_Retriever(), critic=_Critic(), mode="rag")
    result = orch._node_judge_rag({"candidates": candidates, "candidate_contexts": {}})

    assert result["verdicts"] == verdicts
    assert result["tool_calls"] == 1
    assert result["tool_latency_ms"] == 12.5


# ── Full run(): rag mode, end-to-end with fakes only ─────────────────────────

def test_run_rag_mode_end_to_end_produces_run_artifact(monkeypatch):
    from src.vectordb.base import ContextPackage

    candidates = [CandidateSmell(smell_id="a", element_name="f")]
    det_response = LLMResponse(content="{}", model="det-model", prompt_tokens=3, completion_tokens=1, total_tokens=4, latency_ms=5.0)
    crit_response = LLMResponse(content="{}", model="crit-model", prompt_tokens=6, completion_tokens=2, total_tokens=8, latency_ms=9.0)
    verdicts = [Verdict(smell_id="a", element_name="f", confirmed=True, confidence="high", reasoning="r")]

    class _Detector:
        def filter_catalog(self, code):
            return {}

        def run(self, code, timeout=None, catalog=None):
            return candidates, det_response, "det-prompt", "det-sys"

    class _Retriever:
        def run(self, candidates, top_k=3):
            return [ContextPackage(smell_id="a")], 1.0

    class _Critic:
        def run(self, candidate_contexts, candidates, context_packages, timeout=None):
            return verdicts, crit_response, "crit-prompt", "crit-sys"

    monkeypatch.setattr(
        "src.orchestrator.orchestrator.subprocess.run",
        lambda args, **kw: SimpleNamespace(stdout="(defn f [] 1)\n", stderr=""),
    )

    orch = Orchestrator(detector=_Detector(), retriever=_Retriever(), critic=_Critic(), mode="rag")
    artifact, trace = orch.run(code="(defn f [] 1)", file_path="x.clj")

    assert artifact.verdicts == verdicts
    assert artifact.agents.detection.model == "det-model"
    assert artifact.agents.critic.model == "crit-model"
    assert artifact.smell_summary == {"a": 1}
    assert trace["detection"]["system_prompt"] == "det-sys"
    assert trace["critic"]["system_prompt"] == "crit-sys"


def test_run_rag_mode_no_candidates_short_circuits_critic():
    det_response = LLMResponse(content="{}", model="det-model", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)

    class _Detector:
        def filter_catalog(self, code):
            return {}

        def run(self, code, timeout=None, catalog=None):
            return [], det_response, "det-prompt", "det-sys"

    orch = Orchestrator(detector=_Detector(), retriever=SimpleNamespace(), critic=SimpleNamespace(), mode="rag")
    artifact, trace = orch.run(code="(defn f [] 1)", file_path="x.clj")

    assert artifact.verdicts == []
    assert artifact.candidate_smells == []
    assert artifact.agents.critic.model == "skipped"
    assert trace["critic"]["raw_response"] == "SKIPPED"


# ── Full run(): agentic mode, real AgenticCriticAgent + real ToolNode ───────

class _ScriptedChatModel:
    """Stand-in for a LangChain BaseChatModel bound with tools — scripted
    responses, `.invoke()` never touches the network."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, **kwargs):
        self.calls += 1
        return self._responses.pop(0)


def _dataset_with_nested_atoms(tmp_path):
    root = tmp_path / "dataset"
    smell_dir = root / "smells" / "cat" / "nested_atoms"
    smell_dir.mkdir(parents=True)
    (smell_dir / "example_bad_1.md").write_text("```clojure\n(atom (atom 1))\n```", encoding="utf-8")
    return root


def _agentic_orchestrator(monkeypatch, tmp_path, scripted_model, max_tool_rounds=6):
    monkeypatch.setattr(
        "src.agents.agentic_critic.build_chat_model",
        lambda provider, model, api_key: scripted_model,
    )
    store = ExampleStore(dataset_path=str(_dataset_with_nested_atoms(tmp_path)))
    critic = AgenticCriticAgent(
        provider="gemini", model="gemini-flash-latest", example_store=store,
        max_tool_rounds=max_tool_rounds,
    )
    catalog = {"nested_atoms": {"id": "nested_atoms", "name": "Nested Atoms", "summary": "atom in atom"}}

    class _Detector:
        def filter_catalog(self, code):
            return catalog

        def run(self, code, timeout=None, catalog=None):
            candidates = [CandidateSmell(smell_id="nested_atoms", element_name="f")]
            response = LLMResponse(content="{}", model="det-model", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)
            return candidates, response, "det-prompt", "det-sys"

    orch = Orchestrator(
        detector=_Detector(), retriever=None, critic=critic, mode="agentic", catalog=catalog,
    )
    return orch


def test_run_agentic_mode_calls_tool_then_finalizes(monkeypatch, tmp_path):
    tool_call_response = AIMessage(
        content="",
        tool_calls=[{"name": "get_smell_examples", "args": {"smell_ids": ["nested_atoms"]}, "id": "call_1"}],
        usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
    )
    final_response = AIMessage(
        content='{"verdicts": [{"smell_id": "nested_atoms", "element_name": "f", "confirmed": true, "confidence": "high", "reasoning": "matches", "evidence_used": []}]}',
        usage_metadata={"input_tokens": 150, "output_tokens": 30, "total_tokens": 180},
    )
    model = _ScriptedChatModel([tool_call_response, final_response])
    orch = _agentic_orchestrator(monkeypatch, tmp_path, model)

    artifact, trace = orch.run(code="(def x (atom (atom 1)))", file_path="x.clj")

    assert model.calls == 2
    assert len(artifact.verdicts) == 1
    assert artifact.verdicts[0].smell_id == "nested_atoms"
    assert artifact.verdicts[0].confirmed is True
    assert artifact.agents.retrieval.vector_db == "agentic-tool"
    assert artifact.agents.retrieval.calls == 1  # one tool call made
    assert "AI called tool: get_smell_examples" in trace["critic"]["tool_transcript"]


def test_run_agentic_mode_forces_finalize_when_round_budget_exhausted(monkeypatch, tmp_path):
    # Model keeps requesting the same tool forever -> hits max_tool_rounds=1,
    # then force_finalize asks once more (tools unbound) and the model
    # complies with a final JSON answer.
    keeps_asking_for_tools = AIMessage(
        content="",
        tool_calls=[{"name": "get_smell_examples", "args": {"smell_ids": ["nested_atoms"]}, "id": "call_1"}],
        usage_metadata={"input_tokens": 50, "output_tokens": 5, "total_tokens": 55},
    )
    final_after_force = AIMessage(
        content='{"verdicts": [{"smell_id": "nested_atoms", "element_name": "f", "confirmed": false, "confidence": "low", "reasoning": "forced", "evidence_used": []}]}',
        usage_metadata={"input_tokens": 60, "output_tokens": 10, "total_tokens": 70},
    )
    model = _ScriptedChatModel([keeps_asking_for_tools, final_after_force])
    orch = _agentic_orchestrator(monkeypatch, tmp_path, model, max_tool_rounds=1)

    artifact, trace = orch.run(code="(def x (atom (atom 1)))", file_path="x.clj")

    assert artifact.verdicts[0].confirmed is False
    assert artifact.verdicts[0].reasoning == "forced"


def test_run_agentic_mode_retries_on_malformed_final_json_then_succeeds(monkeypatch, tmp_path):
    malformed = AIMessage(content="not valid json", usage_metadata={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12})
    valid = AIMessage(
        content='{"verdicts": [{"smell_id": "nested_atoms", "element_name": "f", "confirmed": true, "confidence": "medium", "reasoning": "ok", "evidence_used": []}]}',
        usage_metadata={"input_tokens": 15, "output_tokens": 5, "total_tokens": 20},
    )
    model = _ScriptedChatModel([malformed, valid])
    orch = _agentic_orchestrator(monkeypatch, tmp_path, model)
    orch.max_retries = 2

    artifact, _ = orch.run(code="(def x (atom (atom 1)))", file_path="x.clj")

    assert artifact.verdicts[0].confidence == "medium"
    assert artifact.retries == 1  # detection 0 + critic 1


def test_run_agentic_mode_raises_after_exhausting_malformed_output_retries(monkeypatch, tmp_path):
    always_malformed = [
        AIMessage(content="still not json", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})
        for _ in range(5)
    ]
    model = _ScriptedChatModel(always_malformed)
    orch = _agentic_orchestrator(monkeypatch, tmp_path, model)
    orch.max_retries = 1

    with pytest.raises(MaxRetriesExceeded):
        orch.run(code="(def x (atom (atom 1)))", file_path="x.clj")
