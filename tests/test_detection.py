from src.agents.detection import Detector
from src.artifact.schema import CandidateSmell, DetectionOutput
from src.llm.base import LLMResponse
from tests.conftest import FakeLLMClient


CATALOG = {
    "unmanaged_resource_io": {"id": "unmanaged_resource_io", "name": "x", "summary": "s", "category": "c"},
    "nested_atoms": {"id": "nested_atoms", "name": "y", "summary": "s2", "category": "c"},
}


def _detector(llm):
    return Detector(llm=llm, catalog=CATALOG)


# ── filter_catalog ────────────────────────────────────────────────────────────

def test_filter_catalog_returns_full_catalog_when_no_filters_loaded():
    d = _detector(FakeLLMClient())
    d.filters = {}
    assert d.filter_catalog("(defn f [] 1)") == CATALOG


def test_filter_catalog_keeps_smell_when_any_required_keyword_present():
    d = _detector(FakeLLMClient())
    d.filters = {"unmanaged_resource_io": ["io/reader", "io/writer"]}
    filtered = d.filter_catalog("(io/reader \"f\")")
    assert "unmanaged_resource_io" in filtered
    assert "nested_atoms" in filtered  # unfiltered smell always kept


def test_filter_catalog_drops_smell_when_no_required_keyword_present():
    d = _detector(FakeLLMClient())
    d.filters = {"unmanaged_resource_io": ["io/reader", "io/writer"]}
    filtered = d.filter_catalog("(+ 1 2)")
    assert "unmanaged_resource_io" not in filtered
    assert "nested_atoms" in filtered


def test_filter_catalog_keeps_smells_with_no_filter_entry_unconditionally():
    d = _detector(FakeLLMClient())
    d.filters = {"unmanaged_resource_io": ["io/reader"]}
    filtered = d.filter_catalog("nothing relevant")
    assert "nested_atoms" in filtered


# ── run() ─────────────────────────────────────────────────────────────────────

def test_run_uses_native_structured_output_when_available():
    candidates = [CandidateSmell(smell_id="nested_atoms", element_name="f")]
    response = LLMResponse(
        content="{}", model="m", prompt_tokens=1, completion_tokens=1,
        total_tokens=2, latency_ms=1.0, json_mode_used=True,
    )
    llm = FakeLLMClient(structured_result=(DetectionOutput(candidates=candidates), response))
    d = _detector(llm)
    d.filters = {}

    result_candidates, result_response, prompt, system = d.run("(atom (atom 1))")

    assert result_candidates == candidates
    assert result_response.json_mode_used is True
    assert len(llm.structured_calls) == 1
    assert len(llm.complete_calls) == 0
    assert "atom (atom 1)" in prompt
    assert system.startswith("You are a Clojure code quality expert")


def test_run_falls_back_to_text_parsing_when_structured_output_fails():
    llm = FakeLLMClient(
        structured_error=RuntimeError("provider does not support structured output"),
        text_content='{"candidates": [{"smell_id": "nested_atoms"}]}',
    )
    d = _detector(llm)
    d.filters = {}

    candidates, response, _, _ = d.run("(atom (atom 1))")

    assert [c.smell_id for c in candidates] == ["nested_atoms"]
    assert len(llm.structured_calls) == 1
    assert len(llm.complete_calls) == 1


def test_run_accepts_pre_filtered_catalog_and_skips_internal_filtering():
    llm = FakeLLMClient(text_content='{"candidates": []}', structured_error=RuntimeError("x"))
    d = _detector(llm)
    d.filters = {"nested_atoms": ["atom"]}  # would drop nested_atoms if applied

    pre_filtered = {"nested_atoms": CATALOG["nested_atoms"]}
    d.run("no atom keyword here", catalog=pre_filtered)

    prompt = llm.structured_calls[0]["prompt"]
    assert "nested_atoms" in prompt  # came straight from the passed-in catalog
    assert "unmanaged_resource_io" not in prompt
