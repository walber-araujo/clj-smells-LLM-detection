from ..llm.base import LLMClient, LLMResponse
from ..catalog.loader import format_catalog_for_prompt
from ..artifact.schema import CandidateSmell, DetectionOutput
from ..artifact.validator import parse_detection_output, MalformedOutputError
import json
import os
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Clojure code quality expert. Your task is to analyze a Clojure source file \
and identify potential code smells from the provided catalog.

Rules:
- Respond ONLY with a valid JSON object containing a "candidates" array.
- Each element of "candidates" must follow this exact structure:
  {
    "smell_id": "<exact id from the catalog>",
    "element_name": "<Name of the smallest named top-level element containing the smell (e.g. name of the defn, defmacro, defmulti, defmethod, or def). If it's a namespace-level smell, output the namespace name.>"
  }
- Only include smells you have reasonable evidence for.
- Return {\"candidates\": []} if no smells are detected.
- Do NOT invent smell IDs — use only ids listed in the catalog.\
"""

class Detector:
    """Single LLM call against the smell catalog — not an agent (no loop,
    no autonomous tool use). Named for what it does, not what it is."""

    def __init__(self, llm: LLMClient, catalog: dict):
        self.llm = llm
        self.catalog = catalog
        self.filters = {}
        
        filters_path = "smells_filters.json"
        if os.path.exists(filters_path):
            try:
                with open(filters_path, "r", encoding="utf-8") as f:
                    self.filters = json.load(f).get("filters", {})
            except Exception as e:
                logger.warning(f"Failed to load filters from {filters_path}: {e}")

    def filter_catalog(self, code: str) -> dict:
        if not self.filters:
            return self.catalog

        filtered_catalog = {}
        original_count = len(self.catalog)
        
        for smell_id, entry in self.catalog.items():
            if smell_id in self.filters:
                required_keywords = self.filters[smell_id]
                # If ANY of the required keywords are in the code, we keep it
                if any(keyword in code for keyword in required_keywords):
                    filtered_catalog[smell_id] = entry
            else:
                # No filter for this smell, always keep
                filtered_catalog[smell_id] = entry
                
        filtered_count = len(filtered_catalog)
        if filtered_count < original_count:
            logger.info(f"[Detection] Pre-filter active: dropped {original_count - filtered_count} impossible smells.")
            
        return filtered_catalog

    def run(
        self,
        code: str,
        timeout: int = 120,
        catalog: dict | None = None,
    ) -> tuple[list[CandidateSmell], LLMResponse, str, str]:
        """`catalog`: pass a pre-filtered catalog (e.g. from a separate
        pre_filter graph node) to skip re-filtering here. Defaults to
        filtering internally, same as before, if omitted."""
        filtered_catalog = catalog if catalog is not None else self.filter_catalog(code)
        catalog_text = format_catalog_for_prompt(filtered_catalog)

        prompt = f"""\
Analyze the Clojure code below for code smells from the catalog.

## Catalog of Clojure Code Smells
{catalog_text}

## Target Code
```clojure
{code}
```

Respond with a JSON object with a "candidates" array listing smells found in the code above."""

        # Try native structured output first; fall back to text parsing
        try:
            parsed_output, response = self.llm.complete_structured(
                prompt,
                schema=DetectionOutput,
                system=SYSTEM_PROMPT,
                timeout=timeout,
            )
            candidates = parsed_output.candidates
            if response.json_mode_used:
                logger.debug("[Detection] Used native structured output (json_mode_used=True).")
        except Exception as exc:
            logger.warning(
                "[Detection] Structured output failed (%s: %s); falling back to text parsing.",
                type(exc).__name__, str(exc)[:120],
            )
            response = self.llm.complete(prompt, system=SYSTEM_PROMPT, timeout=timeout)
            candidates = parse_detection_output(response.content)

        return candidates, response, prompt, SYSTEM_PROMPT
