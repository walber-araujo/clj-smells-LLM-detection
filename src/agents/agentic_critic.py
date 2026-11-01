"""
agentic_critic.py — "just-in-time context" alternative to the static RAG path.

Instead of Retriever pre-fetching examples for every candidate before the
Critic ever runs (src/agents/critic.py + src/vectordb/chroma_client.py), the
agentic Critic decides for itself, per run, whether it needs code examples
and pulls them on demand via tools backed by src/tools/example_lookup.py —
no embeddings, no vector DB.

Only the catalog description (small, stable) is preloaded into the prompt.
Everything else is fetched just-in-time, following the pattern Anthropic
documents in "Effective Context Engineering for AI Agents" (lightweight
references + tools, rather than pre-computed retrieval).

AgenticCriticAgent itself does NOT own a graph — it's a tool/model/prompt
provider. The agent ⇄ tools cycle is wired directly into Orchestrator's own
StateGraph(PipelineState) (src/orchestrator/orchestrator.py), so the whole
pipeline — including this cycle — is one graph, not two. See
ARCHITECTURE_DECISIONS.md for why this replaced an earlier two-graph version.
"""

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from ..artifact.schema import CandidateSmell
from ..llm.base import (
    OPENROUTER_CACHE_BREAKPOINT,
    _mark_cache_breakpoint,
    cache_tokens_from_langchain_usage,
    cost_from_langchain_response,
)
from ..llm.chat_models import build_chat_model
from ..tools.example_lookup import ExampleStore
from .formatting import format_context_package, format_doc_index

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
3. For each candidate: a catalog description (name + summary) already \
included below.

Nothing else is preloaded — no code examples, no reference documents.
</context>

<tools>
You have four tools. Each tool's own description covers exactly what it \
returns and how — use that, not guesswork, to decide what a call will give \
you back. As a starting point for WHEN to reach for each one:
- `get_smell_examples(smell_ids)`: code evidence for a smell_id you already \
  know — the right tool for every candidate below, since you always know \
  the smell_id already. There is no free-text/"unsure which smell" search \
  tool in this toolset.
- `list_doc_sections()` / `get_doc_section(doc, sections)`: reference docs \
  (e.g. a Clojure style guide) for style/idiom questions the code evidence \
  alone won't settle. Most candidates don't need this. `get_doc_section` \
  takes a LIST of sections from one doc — batch every section you want \
  from that doc into one call.
- `get_function_source(function_names)`: source of other functions the \
  candidate code calls, when what they actually do changes your verdict \
  (e.g. does it block, mutate state, close a resource).
</tools>

<tool_use_guidelines>
Call tools for any candidate where the catalog description alone isn't \
enough to judge confidently. Skip them entirely for candidates you're \
already confident about.

Batch aggressively: pass every smell_id you're unsure about into ONE \
`get_smell_examples` call, and every function name you need into ONE \
`get_function_source` call, rather than one call per item. Tool-call \
rounds are expensive — each round resends the ENTIRE conversation so far, \
so the cost of an extra round is much higher than the cost of a bigger \
first one. There's also a hard cap on how many rounds you get; past it, \
you'll be forced to answer with whatever you already have. Front-load: \
figure out everything you're likely to need per candidate and batch it \
into your first 1-2 rounds instead of trickling out one tool call, \
thinking, another tool call.
</tool_use_guidelines>

<output_format>
Once you have everything you need, respond with your final answer:
- Respond ONLY with a valid JSON object containing a "verdicts" array. No \
markdown, no code fences, no explanation outside the JSON.
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
Candidate: implicit_namespace_dependencies, element some.test.ns. Code: `(ns some.test.ns (:require [clojure.test :refer :all]))`. Evidence: real-curated examples of the smell involve production namespaces hiding application symbols; a fetched doc section calls `:refer :all` "acceptable as warranted."
Verdict:
{"smell_id": "implicit_namespace_dependencies", "element_name": "some.test.ns", "reasoning": "The `:refer :all` technically matches the catalog definition, but this is a test namespace referring `clojure.test` — the style guide explicitly calls that usage acceptable, unlike the curated examples' production-code cases.", "confirmed": true, "confidence": "medium", "evidence_used": ["clojure-style-guide.md#prefer-require-over-use"]}
</example>

<example>
Candidate: production_doall, element helper-fn. Code: `(doall (map do-thing xs))` inside a function whose callers and side effects weren't retrieved. Evidence: catalog examples all show `doall` wrapping side-effecting I/O in application code; none resemble this case closely, and no tool call was made to check what `do-thing` actually does.
Verdict:
{"smell_id": "production_doall", "element_name": "helper-fn", "reasoning": "The shape matches `doall` forcing a lazy `map`, but without seeing `do-thing`'s body there's no way to tell whether this forces side effects (the catalog's concern) or just a pure computation, and no catalog example resembles this specific case closely enough to infer it.", "confirmed": false, "confidence": "low", "evidence_used": ["catalog_synthetic:example_bad_1.md"]}
</example>
</examples>\
"""


def _find_function_file(function_name: str, current_file: Optional[Path], search_root: Optional[Path]) -> Optional[Path]:
    """
    Locate which .clj/.cljs/.cljc file under `search_root` defines
    `function_name`, checking `current_file` first (the common case).
    Pure text search (no subprocess) — just a fast pre-filter to pick the
    right file; the actual extraction is done separately via extract.clj
    once a candidate file is found, so precision comes from rewrite-clj,
    not from this regex.
    """
    name_re = re.compile(r"\(def[\w-]*\s+" + re.escape(function_name) + r"\b")

    candidates: list[Path] = []
    if current_file and current_file.exists():
        candidates.append(current_file)
    if search_root and search_root.exists():
        for ext in ("*.clj", "*.cljs", "*.cljc"):
            candidates.extend(p for p in search_root.rglob(ext) if p != current_file)

    for path in candidates:
        try:
            if name_re.search(path.read_text(encoding="utf-8")):
                return path
        except (OSError, UnicodeDecodeError):
            continue
    return None


class AgenticCriticAgent:
    """
    Tool/model/prompt provider for --retrieval agentic. Does NOT run its own
    graph — Orchestrator wires `llm_with_tools` and `tools` directly into its
    own StateGraph (nodes "agent"/"tools"), so the tool-calling cycle lives
    in the same graph as everything else, not a separate one invoked from a
    node. See Orchestrator's docstring and ARCHITECTURE_DECISIONS.md.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        example_store: ExampleStore,
        api_key: Optional[str] = None,
        max_tool_rounds: int = 6,
    ):
        self.provider = provider
        self.model = model
        self.store = example_store
        self.max_tool_rounds = max_tool_rounds

        self._tool_calls = 0
        self._tool_latency_ms = 0.0
        self._current_file_path: Optional[str] = None
        self._current_search_root: Optional[str] = None
        self._file_shown_in_full = False
        self.session_id: Optional[str] = None
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0
        self.cost: Optional[float] = None
        self._examples_sent: dict[str, set[str]] = {}
        self._doc_index_sent = False

        example_store_ref = example_store

        @tool
        def get_smell_examples(smell_ids: list[str]) -> str:
            """Return curated Clojure code examples for one or more smell_ids:
            code WITH the smell (positive) and clean code WITHOUT it (negative).
            Pass ALL the smell_ids you need in a single call — e.g.
            ["misused_threading", "marker_protocol"] — rather than calling this
            once per smell_id. No `limit` — you have no basis to pick one, so
            each call returns a fixed-size batch (a few human-confirmed real
            examples, preferred, plus synthetic ones only where real evidence
            is thin). Calling this again for a smell_id you already asked
            about does NOT resend what you already have — it returns the
            NEXT not-yet-seen batch if more examples exist, or a short "no
            more" notice if that smell is out of examples. Each result ends
            with a count like "(3 of 5 total examples sent so far — 2 more
            available)" so you can judge whether calling again for more
            evidence is worth it, rather than guessing."""
            start = time.time()
            if not smell_ids:
                # A blank tool result breaks the next round's cache
                # breakpoint (D13/D14 follow-up) on top of being useless on
                # its own — always give the model something non-empty back.
                return "No smell_ids provided — pass at least one to look up."
            parts = []
            for smell_id in smell_ids:
                already_sent = self._examples_sent.setdefault(smell_id, set())
                pkg = example_store_ref.get_examples(smell_id, exclude_ids=frozenset(already_sent))
                total = sum(len(v) for v in pkg.examples.values())
                if total > 0:
                    for exs in pkg.examples.values():
                        already_sent.update(ex.id for ex in exs if ex.id)
                    available = example_store_ref.count_available(smell_id)
                    available_total = available["positive"] + available["negative"]
                    sent_count = len(already_sent)
                    remaining = available_total - sent_count
                    progress_note = (
                        f"({sent_count} of {available_total} total examples for this "
                        f"smell sent so far — that's all of them, no need to call "
                        f"again.)" if remaining <= 0 else
                        f"({sent_count} of {available_total} total examples for this "
                        f"smell sent so far — {remaining} more available if you need "
                        f"them.)"
                    )
                    parts.append(f"{format_context_package(pkg)}\n\n{progress_note}")
                elif already_sent:
                    parts.append(
                        f"### [{smell_id}]\nNo more examples — you already have all "
                        f"{len(already_sent)} available for this smell from earlier "
                        f"in this conversation."
                    )
                else:
                    parts.append(f"### [{smell_id}]\nNo examples found. Judge from the catalog description alone.")
            self._tool_latency_ms += (time.time() - start) * 1000
            self._tool_calls += 1
            return "\n\n---\n\n".join(parts)

        @tool
        def list_doc_sections() -> str:
            """Table of contents of available reference documents (e.g. a
            Clojure style guide) — call this first if you suspect a
            style/idiom question that the smell catalog and code examples
            alone won't settle. Most candidates don't need this at all.
            Calling this again this conversation doesn't resend the index —
            it hasn't changed, use the doc/section names you already have."""
            start = time.time()
            self._tool_latency_ms += (time.time() - start) * 1000
            self._tool_calls += 1
            if self._doc_index_sent:
                return "You already fetched the documentation index earlier in this conversation — it hasn't changed, nothing new to send. Use the doc/section names from that earlier result."
            self._doc_index_sent = True
            sections = example_store_ref.list_doc_sections()
            return format_doc_index(sections)

        @tool
        def get_doc_section(doc: str, sections: list[str]) -> str:
            """Return the full text of one or more sections from a reference
            document. Use `doc`/section names exactly as they appeared in
            list_doc_sections()'s output — matches by anchor or by title.
            Call list_doc_sections() first; don't guess doc/section names.
            Pass ALL the sections you want from this doc in ONE call (e.g.
            ["no-single-segment-namespaces", "prefer-require-over-use"]) —
            not one call per section. If you also need sections from a
            different doc, that's a separate call with that doc's name."""
            start = time.time()
            if not sections:
                return "No sections provided — pass at least one section name to look up."
            parts = [example_store_ref.get_doc_section(doc, section) for section in sections]
            self._tool_latency_ms += (time.time() - start) * 1000
            self._tool_calls += 1
            return "\n\n---\n\n".join(parts)

        @tool
        def get_function_source(function_names: list[str]) -> str:
            """Return the full source of other function/def forms called by
            the code under review (not from the dataset) — searches the
            current file first, then the rest of the project. If a name
            truly isn't found anywhere in the project, it's reported as such
            (likely an external library function). Pass ALL the function
            names you need in one call — e.g. ["query-total", "validate-conn"]
            — not one call per function. Give bare names as they appear in
            the call, e.g. "query-total" not "app.db/query-total". Only for
            names actually defined in this project — Clojure/Java core
            special forms and macros (defrecord, defn, defprotocol, let,
            ns, assoc, str, and the like) aren't project code and won't be
            found; you already know what they do."""
            start = time.time()
            if not function_names:
                return "No function_names provided — pass at least one to look up."
            if not self._current_file_path:
                return "No source file available for this run."

            current_file = Path(self._current_file_path)
            search_root = Path(self._current_search_root) if self._current_search_root else None

            parts = []
            for function_name in function_names:
                found_in = _find_function_file(function_name, current_file, search_root)
                if found_in is None:
                    parts.append(
                        f"### {function_name}\n"
                        f"Not found anywhere in the project — likely an external "
                        f"library function, or genuinely undefined."
                    )
                    continue
                if found_in == current_file and self._file_shown_in_full:
                    # The full file is already in the initial prompt for
                    # this run (file-scope candidates) — re-extracting and
                    # re-sending a function already visible there is pure
                    # waste (both the subprocess call and the tokens).
                    parts.append(
                        f"### {function_name}\n"
                        f"Already visible — it's defined in the current file, "
                        f"whose full source was already given to you above."
                    )
                    continue
                try:
                    result = subprocess.run(
                        ["bb", "src/extractor/extract.clj", "function", str(found_in), function_name],
                        capture_output=True, text=True, check=True, timeout=15,
                    )
                    location = "" if found_in == current_file else f" ({found_in})"
                    parts.append(f"### {function_name}{location}\n```clojure\n{result.stdout.strip()}\n```")
                except subprocess.CalledProcessError:
                    parts.append(f"### {function_name}\nMatched by text search in {found_in} but extraction failed.")
                except FileNotFoundError:
                    parts.append("Extraction unavailable: 'bb' (Babashka) not found in PATH.")
                except subprocess.TimeoutExpired:
                    parts.append(f"### {function_name}\nExtraction timed out.")

            self._tool_latency_ms += (time.time() - start) * 1000
            self._tool_calls += 1
            return "\n\n".join(parts)

        self.tools = [
            get_smell_examples, list_doc_sections,
            get_doc_section, get_function_source,
        ]
        self._llm = build_chat_model(provider, model, api_key)
        self.llm_with_tools = self._llm.bind_tools(self.tools)

    # ── Per-run state (Orchestrator calls reset_run once per file) ─────────

    @property
    def tool_calls(self) -> int:
        return self._tool_calls

    @property
    def tool_latency_ms(self) -> float:
        return self._tool_latency_ms

    def reset_run(
        self, file_path: Optional[str], search_root: Optional[str],
        run_id: Optional[str] = None,
    ) -> None:
        """Call once at the start of judging each file — resets the tool-use
        counters and points get_function_source() at the right file/project.

        `run_id`: same identifier as this run's RunArtifact.run_id (see
        Orchestrator.run()). Used to derive a stable OpenRouter `session_id`
        (D13) so every LLM call made while judging THIS file's candidates —
        across however many tool-call rounds it takes — routes to the same
        upstream cache instead of a new one each round. Only meaningful for
        `provider == "openrouter"`; harmless no-op otherwise."""
        self._tool_calls = 0
        self._tool_latency_ms = 0.0
        self._current_file_path = file_path
        self._current_search_root = search_root
        self.session_id = f"critic-agent-{run_id}" if run_id else None
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0
        self.cost = None
        self._examples_sent = {}
        self._doc_index_sent = False
        self._file_shown_in_full = False

    def record_cache_usage(self, response) -> None:
        """D13 observability: accumulate this call's cache read/write tokens
        (if the provider reported any) into this run's running total, so
        Orchestrator can surface it in the final RunArtifact for our own
        analysis. Purely bookkeeping on our side — never sent back to the
        model, doesn't affect what it sees or decides. Extraction itself
        lives in llm/base.py (D24) — shared with LangChainLLMClient, the
        rag/detection path's equivalent normalized-response consumer."""
        cache_read, cache_write = cache_tokens_from_langchain_usage(response)
        self.cache_read_tokens += cache_read
        self.cache_write_tokens += cache_write

    def record_cost(self, response) -> None:
        """D23: accumulate this call's OpenRouter-reported cost, if any —
        see llm/base.py's cost_from_langchain_response() (D24) for where
        `response.response_metadata["token_usage"]["cost"]` is actually
        read and why. None/absent means not reported — left as None, not
        folded into the running total as 0, so a run with no cost data
        isn't shown as free."""
        call_cost = cost_from_langchain_response(response)
        if call_cost is not None:
            self.cost = (self.cost or 0.0) + call_cost

    # ── Prompt construction / output parsing (used by Orchestrator's nodes) ─

    def build_initial_messages(
        self,
        candidate_contexts: dict[str, str],
        candidates: list[CandidateSmell],
        catalog: dict,
    ) -> tuple[list[BaseMessage], str]:
        """Returns (messages, user_prompt) — user_prompt is kept separately
        for the trace file."""
        catalog_parts = []
        seen_smell_ids = set()
        for cand in candidates:
            if cand.smell_id in seen_smell_ids:
                continue
            seen_smell_ids.add(cand.smell_id)
            entry = catalog.get(cand.smell_id)
            if entry:
                catalog_parts.append(f"- **{entry['id']}** — {entry['name']}: {entry['summary']}")
            else:
                catalog_parts.append(f"- **{cand.smell_id}** — (no catalog entry found)")
        catalog_text = "\n".join(catalog_parts)

        has_file_scope = any(
            candidate_contexts.get(f"{c.smell_id}::{c.element_name}") == "__FILE_SCOPE__"
            for c in candidates
        )
        self._file_shown_in_full = has_file_scope
        candidate_parts = []
        if has_file_scope:
            all_candidates_list = "\n".join(
                f"- **{c.smell_id}** (element: {c.element_name})" for c in candidates
            )
            full_file_code = next((c.snippet for c in candidates if c.snippet), "Context not found.")
            candidate_parts.append(
                f"### All Candidates (full file provided — covers all snippets)\n"
                f"{all_candidates_list}\n\n```clojure\n{full_file_code}\n```\n\n"
                f"The full file above already contains the source of every "
                f"function/def defined in it — you already have those, no "
                f"need to call get_function_source for them. That tool is "
                f"only useful here for functions the candidate code calls "
                f"that are NOT defined in this file (e.g. from another "
                f"namespace)."
            )
        else:
            for candidate in candidates:
                key = f"{candidate.smell_id}::{candidate.element_name}"
                ctx_code = candidate_contexts.get(key, "Context not found.")
                candidate_parts.append(
                    f"### Candidate: {candidate.smell_id} | Element: {candidate.element_name}\n"
                    f"```clojure\n{ctx_code}\n```"
                )
        candidates_text = "\n\n".join(candidate_parts)

        user_prompt = f"""\
## Candidate Smells and Code Contexts
{candidates_text}

## Catalog Descriptions
{catalog_text}

Produce a JSON object with a "verdicts" array containing one verdict per candidate smell listed above. Batch get_smell_examples into as few calls as possible for any candidates you're not already confident about."""

        if self.provider == "anthropic":
            # Anthropic prompt caching (see D12): marking a content block
            # `cache_control: {"type": "ephemeral"}` caches everything up to
            # and including that block. The system prompt and this initial
            # message (candidates + catalog) are identical on every one of
            # the agent's tool-call rounds — without this they'd be
            # re-billed at full price on every round, on top of the
            # growing tool-result history (see D6).
            system_content = [{
                "type": "text", "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }]
            human_content = [{
                "type": "text", "text": user_prompt,
                "cache_control": {"type": "ephemeral"},
            }]
            messages = [SystemMessage(content=system_content), HumanMessage(content=human_content)]
        elif self.provider == "openrouter":
            # OpenRouter prompt caching (D13): same idea as the Anthropic
            # branch above, using `prompt_cache_breakpoint` instead of
            # `cache_control` — the field this codebase's installed
            # `langchain-openai` actually preserves end-to-end (verified by
            # reading `_format_message_content` /
            # `_sanitize_chat_completions_content` in
            # langchain_openai/chat_models/base.py), and the one OpenRouter's
            # own docs use for the OpenAI-compatible transport this
            # provider's `ChatOpenAI` client goes through (see D13 sources).
            system_content = [{
                "type": "text", "text": SYSTEM_PROMPT,
                "prompt_cache_breakpoint": OPENROUTER_CACHE_BREAKPOINT,
            }]
            human_content = [{
                "type": "text", "text": user_prompt,
                "prompt_cache_breakpoint": OPENROUTER_CACHE_BREAKPOINT,
            }]
            messages = [SystemMessage(content=system_content), HumanMessage(content=human_content)]
        else:
            messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
        return messages, user_prompt

    def with_cache_breakpoint(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        """OpenRouter only (D13): move the cache breakpoint to the tail of
        the conversation before every `agent` node call.

        The static prefix (system + initial message) already carries a
        breakpoint from `build_initial_messages()`. What changes round to
        round is everything *after* that — each round appends the previous
        round's tool call(s) and tool result(s), then calls the LLM again.
        Marking the LAST message's content as a second breakpoint means
        round N's call reuses everything cached through round N-1 (system +
        initial message + every prior tool result) and only pays full price
        for what's actually new: this round's freshly appended tool
        result(s). Does not mutate `messages` in place — `PipelineState`
        keeps the unmarked originals; only the copy handed to `.invoke()`
        carries the breakpoint.
        """
        if self.provider != "openrouter" or not messages:
            return messages
        last = messages[-1]
        new_content = _mark_cache_breakpoint(last.content)
        if new_content is last.content:
            return messages
        return [*messages[:-1], last.model_copy(update={"content": new_content})]

    def invoke_kwargs(self) -> dict:
        """Extra per-call kwargs for `llm_with_tools.invoke(...)` — currently
        just OpenRouter's `session_id` (D13), passed via `extra_body` (the
        documented langchain-openai mechanism for OpenAI-compatible-provider
        fields that aren't part of the standard OpenAI API; see
        `ChatOpenAI.extra_body`'s docstring, which names OpenRouter
        explicitly). Kept as one stable id per file-run — set once in
        `reset_run()` — so every tool-call round for this file's candidates
        routes to the same upstream cache instead of a fresh one per call."""
        if self.provider == "openrouter" and self.session_id:
            return {"extra_body": {"session_id": self.session_id}}
        return {}

    @staticmethod
    def extract_final_text(messages: list) -> str:
        """Text content of the last AIMessage — the model's final answer
        once it stops requesting tools."""
        ai_messages = [m for m in messages if isinstance(m, AIMessage)]
        content = ai_messages[-1].content
        if isinstance(content, list):
            content = "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return content

    @staticmethod
    def token_usage(messages: list) -> tuple[int, int]:
        """Summed (prompt_tokens, completion_tokens) across every AIMessage
        turn — a multi-turn tool-calling run makes more than one LLM call."""
        prompt_tokens = completion_tokens = 0
        for m in messages:
            if isinstance(m, AIMessage):
                usage = m.usage_metadata or {}
                prompt_tokens += usage.get("input_tokens", 0)
                completion_tokens += usage.get("output_tokens", 0)
        return prompt_tokens, completion_tokens

    @staticmethod
    def build_transcript(messages: list) -> str:
        """Turn-by-turn record of everything after the initial system/user
        messages: tool calls requested, what the tool returned, and any
        intermediate/final AI text. Skips the first two messages (system +
        initial human prompt) since those are already stored separately."""
        parts = []
        turn = 1
        for m in messages[2:]:
            if isinstance(m, AIMessage):
                for tc in (getattr(m, "tool_calls", None) or []):
                    parts.append(f"[Turn {turn}] AI called tool: {tc['name']}({tc['args']})")
                    turn += 1
                text = m.content
                if isinstance(text, list):
                    text = "".join(
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in text
                    )
                if text and text.strip():
                    parts.append(f"[Turn {turn}] AI response:\n{text}")
                    turn += 1
            elif isinstance(m, ToolMessage):
                parts.append(f"[Tool result — {m.name}]\n{m.content}")
        return "\n\n".join(parts)
