from src.agents.critic import Critic
from src.artifact.schema import CandidateSmell, CriticOutput, Verdict
from src.llm.base import LLMResponse
from src.vectordb.base import CodeExample, ContextPackage
from tests.conftest import FakeLLMClient


def _pkg(smell_id, catalog_entry=None):
    pkg = ContextPackage(smell_id=smell_id, catalog_entry=catalog_entry)
    pkg.examples["positive"].append(CodeExample(code="(bad)", label="positive", source="s"))
    return pkg


def test_run_dedupes_context_packages_by_smell_id():
    candidates = [
        CandidateSmell(smell_id="a", element_name="f1"),
        CandidateSmell(smell_id="a", element_name="f2"),
    ]
    packages = [_pkg("a"), _pkg("a")]  # two candidates share smell_id "a"
    verdicts_out = [
        Verdict(smell_id="a", element_name="f1", confirmed=True, confidence="high", reasoning="r"),
        Verdict(smell_id="a", element_name="f2", confirmed=False, confidence="low", reasoning="r"),
    ]
    response = LLMResponse(content="{}", model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)
    llm = FakeLLMClient(structured_result=(CriticOutput(verdicts=verdicts_out), response))
    critic = Critic(llm=llm)

    contexts = {"a::f1": "(bad code 1)", "a::f2": "(bad code 2)"}
    verdicts, _, prompt, _ = critic.run(contexts, candidates, packages)

    assert verdicts == verdicts_out
    # evidence for smell_id "a" should appear exactly once, not twice
    assert prompt.count("### [a]") == 1


def test_run_embeds_full_file_once_when_any_candidate_is_file_scoped():
    candidates = [
        CandidateSmell(smell_id="ns_smell", element_name="my.ns"),
        CandidateSmell(smell_id="fn_smell", element_name="helper"),
    ]
    contexts = {
        "ns_smell::my.ns": "__FILE_SCOPE__",
        "fn_smell::helper": "(defn helper [] 1)",
    }
    candidates[0].snippet = "(ns my.ns)\n(defn helper [] 1)"
    response = LLMResponse(content="{}", model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)
    llm = FakeLLMClient(structured_result=(CriticOutput(verdicts=[]), response))
    critic = Critic(llm=llm)

    _, _, prompt, _ = critic.run(contexts, candidates, [_pkg("ns_smell"), _pkg("fn_smell")])

    assert "All Candidates (full file provided" in prompt
    assert prompt.count("```clojure\n(ns my.ns)") == 1
    # individual per-candidate snippet blocks should NOT also appear
    assert "### Candidate: fn_smell" not in prompt


def test_run_embeds_individual_snippets_when_no_file_scope_candidate():
    candidates = [CandidateSmell(smell_id="a", element_name="f")]
    contexts = {"a::f": "(defn f [] 1)"}
    response = LLMResponse(content="{}", model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)
    llm = FakeLLMClient(structured_result=(CriticOutput(verdicts=[]), response))
    critic = Critic(llm=llm)

    _, _, prompt, _ = critic.run(contexts, candidates, [_pkg("a")])

    assert "### Candidate: a | Element: f" in prompt
    assert "(defn f [] 1)" in prompt


def test_run_falls_back_to_text_parsing_when_structured_output_fails():
    candidates = [CandidateSmell(smell_id="a", element_name="f")]
    contexts = {"a::f": "(defn f [] 1)"}
    llm = FakeLLMClient(
        structured_error=RuntimeError("no structured support"),
        text_content='{"verdicts": [{"smell_id": "a", "element_name": "f", "confirmed": true, "confidence": "high", "reasoning": "r"}]}',
    )
    critic = Critic(llm=llm)

    verdicts, _, _, _ = critic.run(contexts, candidates, [_pkg("a")])

    assert verdicts[0].smell_id == "a"
    assert len(llm.complete_calls) == 1
