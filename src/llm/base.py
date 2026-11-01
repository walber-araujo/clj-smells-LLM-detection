from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# D13/D17: OpenRouter's explicit-caching breakpoint format for the OpenAI-
# compatible transport (`{"mode": "explicit"}` on a text block's
# `prompt_cache_breakpoint` key) — see openrouter.ai/docs/guides/best-practices/prompt-caching.
# Shared here (not just in agentic_critic.py) so any client in this module
# that wants to mark a breakpoint uses the exact same literal, not a copy
# that can drift.
OPENROUTER_CACHE_BREAKPOINT = {"mode": "explicit"}


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    json_mode_used: bool = field(default=False)
    # D17 observability, mirrors AgentLLMMetrics — 0 unless a client below
    # actually populates it from the provider's response. Not sent back to
    # the model, just recorded for our own analysis of whether prompt
    # caching (D12/D13) is actually happening on THIS call.
    cache_read_tokens: int = field(default=0)
    cache_write_tokens: int = field(default=0)
    # D23: OpenRouter-reported cost for this exact call (their `usage.cost`
    # field, in their own credit unit — see D23 in ARCHITECTURE_DECISIONS.md
    # for what is and isn't verified about that unit). `None` — not 0 — when
    # the provider didn't report it, so a genuinely free/zero-cost call
    # can't be confused with "we don't know."
    cost: Optional[float] = field(default=None)


def cache_tokens_from_langchain_usage(response) -> tuple[int, int]:
    """(cache_read, cache_write) from a LangChain `AIMessage.usage_metadata`
    — the cross-provider-normalized usage field every `BaseChatModel`
    populates (D24), as opposed to `response_metadata`, which is a raw,
    provider-shaped passthrough. `None`/absent `usage_metadata`, or its
    `input_token_details` sub-dict, means "not reported by this response" —
    treated as 0, not an error."""
    usage = getattr(response, "usage_metadata", None) or {}
    details = usage.get("input_token_details") or {}
    return details.get("cache_read", 0) or 0, details.get("cache_creation", 0) or 0


def cost_from_langchain_response(response) -> Optional[float]:
    """OpenRouter's `usage.cost` (D23) as surfaced through LangChain: not
    part of `usage_metadata`'s normalized shape, so read from
    `response_metadata["token_usage"]["cost"]` instead — the raw
    provider usage dict LangChain passes through largely as-is (confirmed
    directly against `ChatOpenAI`'s `.invoke()` pipeline in D23). Returns
    None — not 0 — when absent, so a genuinely free/zero-cost call can't be
    confused with "we don't know."."""
    token_usage = (getattr(response, "response_metadata", None) or {}).get("token_usage") or {}
    return token_usage.get("cost")


def _mark_cache_breakpoint(content):
    """Return `content` with an OpenRouter `prompt_cache_breakpoint` set on
    its last (or only) text block. Strings are promoted to a one-block list
    first. Returns `content` unchanged (same object) if there's nothing
    eligible to mark, so callers can cheaply check `is` to detect a no-op."""
    if isinstance(content, str):
        if not content:
            return content
        return [{
            "type": "text", "text": content,
            "prompt_cache_breakpoint": OPENROUTER_CACHE_BREAKPOINT,
        }]
    if isinstance(content, list) and content:
        last = content[-1]
        if isinstance(last, dict) and last.get("type") == "text" and "text" in last:
            marked = [*content[:-1], {**last, "prompt_cache_breakpoint": OPENROUTER_CACHE_BREAKPOINT}]
            return marked
    return content


class LLMClient(ABC):
    """
    Abstract base class for LLM providers.

    Implementations must normalize the provider's response into LLMResponse,
    including token usage. Each provider exposes usage differently:
      - OpenAI:    response.usage.{prompt_tokens, completion_tokens}
      - Anthropic: response.usage.{input_tokens, output_tokens}
      - Gemini:    response.usage_metadata.{prompt_token_count, candidates_token_count}
    """

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> LLMResponse:
        """Send prompt and return a normalized LLMResponse."""
        ...

    def complete_structured(
        self,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> tuple[T, LLMResponse]:
        """
        Send prompt and return a validated Pydantic model instance.

        Default implementation calls complete() and parses the text output.
        Providers that support native JSON/structured output should override
        this method to use their API's built-in capability instead.

        Returns (parsed_model_instance, LLMResponse).
        """
        from ..artifact.validator import _extract_json
        import json

        response = self.complete(prompt, system=system, timeout=timeout)
        json_str = _extract_json(response.content)
        data = json.loads(json_str)
        parsed = schema.model_validate(data)
        return parsed, response
