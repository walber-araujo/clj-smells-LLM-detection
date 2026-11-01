import logging

from ..llm.base import LLMClient, LLMResponse
from ..vectordb.base import ContextPackage, CodeExample
from ..artifact.schema import Verdict, CandidateSmell, CriticOutput
from ..artifact.validator import parse_critic_output
from .formatting import format_context_package

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
<role>
You are a senior Clojure code reviewer performing a final quality judgment \
on candidate code smells.
</role>

<context>
You will receive:
1. The isolated Clojure code contexts where the candidate smells were detected.
2. A set of candidate smells detected by a previous agent. Keep in mind that \
these candidates were identified by a preliminary automated detection tool \
and are not a final answer; they may contain false positives. Your job is \
to independently verify them to avoid bias.
3. For each candidate: a catalog description and supporting evidence (code \
examples WITH the smell, clean code WITHOUT it, refactoring suggestions, \
expert comments).

Your task: produce a final verdict for every candidate smell listed.
</context>

<output_format>
- Respond ONLY with a valid JSON object containing a "verdicts" array. No \
markdown, no code fences, no explanation.
- Each element of "verdicts" must follow this exact structure:
  {
    "smell_id": "<smell id>",
    "element_name": "<name of the enclosing form or namespace>",
    "reasoning": "<STEP-BY-STEP REASONING FIRST: Keep it brief, direct, and under 2 sentences. Analyze the target lines, compare with evidence, and formulate argument BEFORE deciding.>",
    "confirmed": <true or false>,
    "confidence": "<high | medium | low>",
    "evidence_used": ["<source label 1>", "<source label 2>"]
  }
- Produce exactly one verdict per candidate, even the ones you cannot confirm.
- Base your judgment on the evidence provided, not general knowledge alone.
</output_format>

<confidence_rubric>
`confidence` is not a mood, it's about whether a caveat actually changes \
the verdict:
- `high`: the evidence matches cleanly and you have no real caveat about \
  applying it here.
- `medium`: use ONLY when a specific contextual factor could plausibly \
  flip the verdict (e.g. this is test/example code where the convention \
  differs from production code, or the case is a smaller/weaker instance \
  of the pattern than your examples show) — name that factor in the \
  reasoning, don't just gesture at nuance in general.
- `low`: the evidence is thin, absent, or conflicting, or you had to guess \
  past a real gap.
</confidence_rubric>

<examples>
These are illustrative, not from any real file — they show the calibration \
this rubric asks for, not the specific smells or code you'll actually see.

<example>
Candidate: unnecessary_into, element get-ids. Code: `(defn get-ids [xs] (into [] (map :id xs)))`. Evidence: catalog examples show `(into [] coll)` flagged in favor of `vec`/`mapv`.
Verdict:
{"smell_id": "unnecessary_into", "element_name": "get-ids", "reasoning": "`(into [] (map :id xs))` is exactly the catalog's flagged pattern — `(mapv :id xs)` is the direct, idiomatic replacement, with no complicating factor.", "confirmed": true, "confidence": "high", "evidence_used": ["catalog_synthetic:example_bad_1.md"]}
</example>

<example>
Candidate: implicit_namespace_dependencies, element some.test.ns. Code: `(ns some.test.ns (:require [clojure.test :refer :all]))`. Evidence: real-curated examples of the smell involve production namespaces hiding application symbols; a supplied doc excerpt calls `:refer :all` "acceptable as warranted."
Verdict:
{"smell_id": "implicit_namespace_dependencies", "element_name": "some.test.ns", "reasoning": "The `:refer :all` technically matches the catalog definition, but this is a test namespace referring `clojure.test` — the style guide explicitly calls that usage acceptable, unlike the curated examples' production-code cases.", "confirmed": true, "confidence": "medium", "evidence_used": ["clojure-style-guide.md#prefer-require-over-use"]}
</example>

<example>
Candidate: production_doall, element helper-fn. Code: `(doall (map do-thing xs))`, with no evidence supplied about what `do-thing` actually does. Evidence: catalog examples all show `doall` wrapping side-effecting I/O in application code; none resemble this case closely.
Verdict:
{"smell_id": "production_doall", "element_name": "helper-fn", "reasoning": "The shape matches `doall` forcing a lazy `map`, but without knowing `do-thing`'s body there's no way to tell whether this forces side effects (the catalog's concern) or just a pure computation, and no supplied example resembles this specific case closely enough to infer it.", "confirmed": false, "confidence": "low", "evidence_used": ["catalog_synthetic:example_bad_1.md"]}
</example>
</examples>\
"""

class Critic:
    """Single LLM call over pre-fetched evidence — not an agent (no loop,
    no tool use). See AgenticCriticAgent for the version that actually is one."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(
        self,
        candidate_contexts: dict[str, str],
        candidates: list[CandidateSmell],
        context_packages: list[ContextPackage],
        timeout: int = 120,
    ) -> tuple[list[Verdict], LLMResponse, str, str]:

        # 1. Group evidence by unique smell_id to avoid repeating tokens
        unique_packages = {}
        for pkg in context_packages:
            if pkg.smell_id not in unique_packages:
                unique_packages[pkg.smell_id] = pkg

        evidence_parts = []
        for pkg in unique_packages.values():
            evidence_parts.append(format_context_package(pkg))

        evidence_text = "\n\n---\n\n".join(evidence_parts)

        # 2. Check if any candidate requires the full file
        has_file_scope = any(
            candidate_contexts.get(f"{c.smell_id}::{c.element_name}") == "__FILE_SCOPE__"
            for c in candidates
        )

        # 3. Build candidate section
        candidate_parts = []
        if has_file_scope:
            # Full file already covers all candidates — list all, embed file once
            all_candidates_list = "\n".join(
                f"- **{c.smell_id}** (element: {c.element_name})"
                for c in candidates
            )
            full_file_code = next(
                (c.snippet for c in candidates if c.snippet),
                "Context not found."
            )
            candidate_parts.append(
                f"### All Candidates (full file provided — covers all snippets)\n"
                f"{all_candidates_list}\n\n"
                f"```clojure\n{full_file_code}\n```"
            )
        else:
            # No file-scope candidate: embed individual snippets per candidate
            for candidate in candidates:
                key = f"{candidate.smell_id}::{candidate.element_name}"
                ctx_code = candidate_contexts.get(key, "Context not found.")
                candidate_parts.append(
                    f"### Candidate: {candidate.smell_id} | Element: {candidate.element_name}\n"
                    f"```clojure\n{ctx_code}\n```"
                )

        candidates_text = "\n\n".join(candidate_parts)

        prompt = f"""\
## Candidate Smells and Code Contexts
{candidates_text}

## Evidence from Catalog & Vector DB
{evidence_text}

Produce a JSON object with a \"verdicts\" array containing one verdict per candidate smell listed above."""

        # Try native structured output first; fall back to text parsing
        try:
            parsed_output, response = self.llm.complete_structured(
                prompt,
                schema=CriticOutput,
                system=SYSTEM_PROMPT,
                timeout=timeout,
            )
            verdicts = parsed_output.verdicts
            if response.json_mode_used:
                logger.debug("[Critic] Used native structured output (json_mode_used=True).")
        except Exception as exc:
            logger.warning(
                "[Critic] Structured output failed (%s: %s); falling back to text parsing.",
                type(exc).__name__, str(exc)[:120],
            )
            response = self.llm.complete(prompt, system=SYSTEM_PROMPT, timeout=timeout)
            verdicts = parse_critic_output(response.content)

        return verdicts, response, prompt, SYSTEM_PROMPT

