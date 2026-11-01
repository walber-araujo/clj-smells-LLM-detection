from src.llm.base import LLMClient, LLMResponse


class FakeLLMClient(LLMClient):
    """Test double for LLMClient — never touches the network. Configure
    `structured_result`/`structured_error` for complete_structured() and
    `text_content` for the complete() fallback path."""

    def __init__(self, structured_result=None, structured_error=None, text_content=""):
        self.structured_result = structured_result
        self.structured_error = structured_error
        self.text_content = text_content
        self.complete_calls = []
        self.structured_calls = []

    def complete(self, prompt, system=None, timeout=None):
        self.complete_calls.append({"prompt": prompt, "system": system, "timeout": timeout})
        return LLMResponse(
            content=self.text_content, model="fake-model", prompt_tokens=1,
            completion_tokens=1, total_tokens=2, latency_ms=1.0,
        )

    def complete_structured(self, prompt, schema, system=None, timeout=None):
        self.structured_calls.append({"prompt": prompt, "schema": schema, "system": system, "timeout": timeout})
        if self.structured_error is not None:
            raise self.structured_error
        return self.structured_result
