import pytest
from pydantic import ValidationError

from src.artifact.schema import (
    AgentLLMMetrics,
    AgentRetrievalMetrics,
    AgentsMetrics,
    CandidateSmell,
    CriticOutput,
    DetectionOutput,
    RunArtifact,
    Verdict,
)


def test_agent_llm_metrics_defaults():
    m = AgentLLMMetrics(
        model="gemini-flash-latest",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        latency_ms=100.0,
    )
    assert m.retries_used == 0
    assert m.json_mode_used is False
    assert m.cache_read_tokens == 0
    assert m.cache_write_tokens == 0
    assert m.cost is None


def test_candidate_smell_optional_fields_default_none():
    c = CandidateSmell(smell_id="unnecessary_into")
    assert c.element_name is None
    assert c.snippet is None


def test_verdict_requires_valid_confidence_literal():
    with pytest.raises(ValidationError):
        Verdict(
            smell_id="x", confirmed=True, confidence="very-high", reasoning="r",
        )


def test_verdict_evidence_used_defaults_to_empty_list():
    v = Verdict(smell_id="x", confirmed=False, confidence="low", reasoning="r")
    assert v.evidence_used == []


def test_detection_output_wraps_candidate_list():
    out = DetectionOutput(candidates=[{"smell_id": "a"}, {"smell_id": "b"}])
    assert [c.smell_id for c in out.candidates] == ["a", "b"]


def test_critic_output_wraps_verdict_list():
    out = CriticOutput(verdicts=[
        {"smell_id": "a", "confirmed": True, "confidence": "high", "reasoning": "r"}
    ])
    assert out.verdicts[0].smell_id == "a"


def _metrics(**overrides):
    base = dict(model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)
    base.update(overrides)
    return AgentLLMMetrics(**base)


def test_run_artifact_generates_run_id_and_timestamp_when_omitted():
    artifact = RunArtifact(
        file="foo.clj",
        agents=AgentsMetrics(
            detection=_metrics(),
            retrieval=AgentRetrievalMetrics(vector_db="mock", calls=1, latency_ms=1.0),
            critic=_metrics(),
        ),
        total_latency_ms=10.0,
        retries=0,
        candidate_smells=[],
        verdicts=[],
    )
    assert artifact.run_id
    assert artifact.timestamp.endswith("Z")
    assert artifact.smell_summary == {}


def test_run_artifact_round_trips_through_json():
    artifact = RunArtifact(
        file="foo.clj",
        agents=AgentsMetrics(
            detection=_metrics(),
            retrieval=AgentRetrievalMetrics(vector_db="mock", calls=1, latency_ms=1.0),
            critic=_metrics(cost=0.002),
        ),
        total_latency_ms=10.0,
        retries=0,
        candidate_smells=[CandidateSmell(smell_id="x", element_name="f")],
        verdicts=[Verdict(smell_id="x", element_name="f", confirmed=True, confidence="high", reasoning="r")],
    )
    dumped = artifact.model_dump_json()
    restored = RunArtifact.model_validate_json(dumped)
    assert restored.candidate_smells[0].smell_id == "x"
    assert restored.agents.critic.cost == 0.002
