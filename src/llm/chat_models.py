from typing import Optional


def build_chat_model(provider: str, model: str, api_key: Optional[str]):
    """LangChain chat model factory shared by every LLM call site in this
    project (D24) — the non-agentic path's LangChainLLMClient
    (langchain_client.py) and the agentic Critic's tool-bound model
    (agents/agentic_critic.py) both build on this, instead of each having
    its own per-provider factory."""
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0)
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=api_key, temperature=0)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        # No `temperature` here on purpose (D15): Anthropic's own docs state
        # that setting temperature/top_p/top_k to a non-default value
        # returns a 400 error on Claude Sonnet 5 — this constraint didn't
        # exist for older Sonnet models, so `temperature=0` used to be safe
        # here and now breaks the request outright on Sonnet 5.
        # `max_tokens=8192` (D15/D24): the bespoke AnthropicClient this
        # factory replaced raised it from LangChain's/the SDK's lower
        # default for the same reason — on models with adaptive thinking on
        # by default, thinking and the response text share this budget, and
        # a tight max_tokens can produce an almost-all-thinking response
        # truncated before the actual JSON output.
        return ChatAnthropic(model=model, api_key=api_key, max_tokens=8192)
    if provider == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model, api_key=api_key,
            base_url="https://openrouter.ai/api/v1", temperature=0,
        )
    if provider == "ollama":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model, api_key="ollama",
            base_url="http://localhost:11434/v1", temperature=0,
        )
    raise ValueError(f"Unknown provider for chat model: '{provider}'")
