from datetime import datetime
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field
import uuid


class AgentLLMMetrics(BaseModel):
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    retries_used: int = 0
    json_mode_used: bool = False      # True when native structured output was used
    # D13 prompt-caching observability (agentic critic, OpenRouter path only
    # so far) — recorded for our own analysis, never sent back to the model.
    # Both 0 for any agent/mode that doesn't track this (detection, rag-mode
    # critic, non-openrouter providers).
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    # D23: OpenRouter's own reported cost for this agent's calls (their
    # `usage.cost`, summed across every call it made — see D23 for what's
    # verified about the unit). None when not reported/not tracked for this
    # agent's provider — kept distinct from 0 (genuinely free/zero cost).
    cost: Optional[float] = None


class AgentRetrievalMetrics(BaseModel):
    vector_db: str
    calls: int
    latency_ms: float


class AgentsMetrics(BaseModel):
    """Typed container for all agent metrics — replaces dict[str, Any]."""
    detection: AgentLLMMetrics
    retrieval: AgentRetrievalMetrics
    critic: AgentLLMMetrics


class CandidateSmell(BaseModel):
    smell_id: str
    element_name: Optional[str] = None
    snippet: Optional[str] = None


# ── Structured output wrappers ────────────────────────────────────────────────
# LLMs with JSON mode cannot return a bare list — they require a top-level
# object. These wrappers allow complete_structured() to be used with list
# outputs via a single envelope field.

class DetectionOutput(BaseModel):
    """Wrapper for Detector structured output (list of candidates)."""
    candidates: list[CandidateSmell] = Field(
        description="List of candidate smells detected in the code."
    )


class Verdict(BaseModel):
    smell_id: str
    element_name: Optional[str] = None
    confirmed: bool
    confidence: Literal["high", "medium", "low"]
    reasoning: str                    # Chain-of-Thought
    evidence_used: list[str] = Field(default_factory=list)


class CriticOutput(BaseModel):
    """Wrapper for Critic structured output (list of verdicts)."""
    verdicts: list[Verdict] = Field(
        description="One verdict per candidate smell."
    )


class RunArtifact(BaseModel):
    file: str
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    agents: AgentsMetrics             # fully typed, replaces dict[str, Any]
    total_latency_ms: float
    retries: int
    smell_summary: dict[str, int] = Field(default_factory=dict)

    candidate_smells: list[CandidateSmell]
    verdicts: list[Verdict]
