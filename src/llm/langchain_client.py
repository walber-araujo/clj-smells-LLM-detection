import time
from typing import Optional, Type

from langchain_core.messages import HumanMessage, SystemMessage

from .base import (
    LLMClient,
    LLMResponse,
    T,
    _mark_cache_breakpoint,
    cache_tokens_from_langchain_usage,
    cost_from_langchain_response,
)
from .chat_models import build_chat_model


class LangChainLLMClient(LLMClient):
    """
    Single LLMClient implementation for every supported provider (D24),
    built on the same LangChain BaseChatModel factory (build_chat_model())
    the agentic Critic uses for tool-calling — replaces what used to be one
    bespoke SDK-wrapping class per provider.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        use_prompt_cache: bool = False,
    ):
        """`use_prompt_cache`: OpenRouter only (D17) — mark the system
        message with an explicit `prompt_cache_breakpoint`. This client is
        single-shot (one call per `complete()`, no growing multi-round
        conversation like the agentic Critic has), so the only thing worth
        caching is the system prompt when it's identical across *separate*
        `complete()` calls — i.e. when this client is reused across
        multiple files in a batch run. A no-op for every other provider."""
        self.provider = provider
        self.model = model
        self._use_prompt_cache = use_prompt_cache
        self._llm = build_chat_model(provider, model, api_key)

    def _build_messages(self, prompt: str, system: Optional[str]) -> list:
        messages = []
        if system:
            if self.provider == "openrouter" and self._use_prompt_cache:
                messages.append(SystemMessage(content=_mark_cache_breakpoint(system)))
            else:
                messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        return messages

    def _resolve_model_name(self, response) -> str:
        """Prefer the resolved/versioned model name the provider echoed back
        (e.g. "claude-x-20260101" for a request of "claude-x") when present
        in `response_metadata`; fall back to the name this client was
        configured with (some providers, e.g. Ollama, don't reliably echo
        one back)."""
        metadata = getattr(response, "response_metadata", None) or {}
        return metadata.get("model_name") or metadata.get("model") or self.model

    @staticmethod
    def _normalize_content(content) -> str:
        if isinstance(content, list):
            return "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return content or ""

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> LLMResponse:
        messages = self._build_messages(prompt, system)
        invoke_kwargs = {"timeout": timeout} if timeout else {}

        start = time.time()
        response = self._llm.invoke(messages, **invoke_kwargs)
        latency_ms = (time.time() - start) * 1000

        usage = response.usage_metadata or {}
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        cache_read, cache_write = cache_tokens_from_langchain_usage(response)

        return LLMResponse(
            content=self._normalize_content(response.content),
            model=self._resolve_model_name(response),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage.get("total_tokens", prompt_tokens + completion_tokens),
            latency_ms=latency_ms,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost=cost_from_langchain_response(response),
        )

    def complete_structured(
        self,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> tuple[T, LLMResponse]:
        """Tries LangChain's `with_structured_output()` first — the
        provider-native mechanism (tool-calling under the hood for
        Anthropic/Gemini, native JSON schema for OpenAI, JSON mode for
        OpenRouter/Ollama); LangChain picks the right one per provider, so
        this client doesn't have to. Falls back to the base class's
        text-parse path (via `complete()`) on any failure — mirrors the
        try/native-then-fallback pattern every per-provider client used
        before this class replaced them (D24)."""
        try:
            messages = self._build_messages(prompt, system)
            invoke_kwargs = {"timeout": timeout} if timeout else {}
            structured_llm = self._llm.with_structured_output(schema, include_raw=True)

            start = time.time()
            raw_response = structured_llm.invoke(messages, **invoke_kwargs)
            latency_ms = (time.time() - start) * 1000

            parsed = raw_response["parsed"]
            if parsed is None:
                raise ValueError("with_structured_output() returned no parsed result")
            ai_message = raw_response["raw"]

            usage = ai_message.usage_metadata or {}
            prompt_tokens = usage.get("input_tokens", 0)
            completion_tokens = usage.get("output_tokens", 0)
            cache_read, cache_write = cache_tokens_from_langchain_usage(ai_message)

            content = self._normalize_content(ai_message.content)
            if not content.strip():
                # with_structured_output() often answers via a tool call
                # rather than text — content is then empty even though
                # `parsed` is populated correctly. Reconstruct something
                # real for the trace instead of leaving it blank.
                content = parsed.model_dump_json(indent=2)

            llm_response = LLMResponse(
                content=content,
                model=self._resolve_model_name(ai_message),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=usage.get("total_tokens", prompt_tokens + completion_tokens),
                latency_ms=latency_ms,
                json_mode_used=True,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
                cost=cost_from_langchain_response(ai_message),
            )
            return parsed, llm_response
        except Exception:
            return super().complete_structured(prompt, schema, system=system, timeout=timeout)
