# Architecture Decisions

This document records the design decisions behind the detection pipeline
(`main.py` → `Orchestrator` → Detection / Retrieval / Critic agents), why
each one was made, and the academic/industry sources that back it. It covers
every stage of the workflow, not just retrieval — and closes with an explicit
validation of whether **Agent Skills** should be adopted.

Scope: this is a living record. Update it when a decision changes or a new
one is made — don't let it drift from the code.

---

## 1. Pipeline overview

```
.clj file
   │
   ▼
[Detector]         — LLM scans the file against the 34-smell catalog, returns candidates
   │
   ▼
[Extraction]       — Babashka + rewrite-clj pulls the exact AST-scoped code per candidate
   │
   ▼
[Retrieval]        — two interchangeable strategies, selected via --retrieval:
   │                   "agentic" (default): AgenticCriticAgent fetches on demand via tools (no embeddings)
   │                   "rag"              : Retriever pre-fetches from ChromaDB (embeddings) — pass explicitly
   ▼
[Critic]           — judges each candidate with the retrieved evidence, Chain-of-Thought
   │                  reasoning, structured JSON verdict
   ▼
RunArtifact (JSON) + trace (.md)
```

Both retrieval strategies are kept side by side (`--retrieval agentic|rag`) —
this was a deliberate choice (§D3) so the pipeline itself can be used to
produce a controlled before/after comparison, not just argued about. Default
is `agentic`; `rag` must be passed explicitly.

Of `Detector` / `Retriever` / `Critic` / `AgenticCriticAgent`, only the last
is an agent in the strict sense used throughout this document — it's the
only one that decides for itself whether/when to act. The other three keep
the word "Agent" out of their names on purpose; see §D1.

The whole pipeline — including the agentic Critic's tool-calling cycle — is
**one** LangGraph graph, not two; see §D11.

---

## 2. Data organization reference

Where each step's data actually lives and how it's read — as opposed to §3
below, which covers *why* it's organized this way. Keep this in sync with
the code; it's a reference, not a decision record.

### 2.1 — Detector

Two files, both at the repo root, loaded by `src/catalog/loader.py` and
`src/agents/detection.py`:

- **`smells_catalog.json`** (full) / **`smells_catalog_short.json`**
  (shortened — this is the one actually sent in the Detector's prompt).
  Same schema: `{"categories": [{"id", "label", "description", "smells":
  [{"id", "name", "summary"}]}]}`. `load_catalog()` flattens this into a
  flat `smell_id → {id, name, summary, category}` dict, discarding the
  category nesting. `format_catalog_for_prompt()` renders that dict as one
  bullet per smell: `- [id] summary`.
- **`smells_filters.json`** — `{"filters": {smell_id: [keyword, ...]}}`.
  `Detector.filter_catalog(code)` drops a smell if it has a keyword list
  and *none* of its keywords appear as a substring of the code — e.g.
  `blocking_inside_go` requires `"(go "` or `"core.async"` to even be
  considered. Smells with no entry in `filters` are never dropped. Plain
  substring check, no regex, no LLM — see D10.

Both files are read fresh per `Detector` construction / `filter_catalog()`
call; no caching layer — they're small enough (~12KB / ~8KB / ~1KB) that
this has never been worth optimizing.

### 2.2 — Critic, `--retrieval rag`

Evidence arrives pre-packaged as `ContextPackage` objects
(`src/vectordb/base.py`), one per candidate:
`{smell_id, catalog_entry: dict | None, examples: {positive, negative,
refactoring, survey_comments, docs: list[CodeExample]}}`.
`CodeExample` = `{code, label, source, description}`.

Built by `ChromaVectorDBClient.query()` from the `clj_smells` Chroma
collection — metadata per document: `smell_id`, `label`, `source`,
`origin_type`, `project`, `file_name`, `target_element`, `reasoning`,
`reasoning_verdict` (full schema documented in the module docstring at the
top of `src/vectordb/chroma_client.py`). `Critic.run()` renders
`ContextPackage`s to prompt text via `format_context_package()`
(`src/agents/formatting.py`), grouped by label with human-readable titles.

### 2.3 — Critic, `--retrieval agentic` (default)

Nothing is pre-packaged. `AgenticCriticAgent`'s tools call straight into
`ExampleStore` (`src/tools/example_lookup.py`), which reads three sources
directly off disk, on every call (no index — see D4):

- `clj-smells-dataset/smells/<category>/<smell_id>/example_{bad,good}_*.md`
  — synthetic examples. First fenced ```clojure block in the file is the
  code; `bad`/`good` in the filename sets the label.
- `clj-smells-dataset/exports/rag_chunks_draft.jsonl` — one JSON object per
  line, real code confirmed by a human curator. Filtered by `smell_id` match
  and `smell_verdict == "confirmed"`.
- `clj-smells-dataset/docs/*.md` — reference documents (e.g. the Clojure
  style guide), indexed by Markdown heading (`#`/`##`/...), with an optional
  `[#anchor]` tag for precise lookup. Convention documented separately in
  `clj-smells-dataset/docs/README.md` (see D5).

Catalog descriptions (name + summary, same flat dict as §2.1) are the one
piece that *is* preloaded here, directly into the prompt via
`AgenticCriticAgent.build_initial_messages()` — small and stable enough
that fetching it on demand wouldn't be worth a tool round-trip.

---

## 3. Decision log

### D1 — Decompose the pipeline into sequential single-purpose steps

Detector → Extraction → Retrieval → Critic, each with one job, wired by
`Orchestrator.run()`.

Naming: `Detector`, `Retriever`, and `Critic` deliberately don't carry
"Agent" in their names — each is one deterministic step (an LLM call, or in
`Retriever`'s case not even that), not something that decides for itself
whether/when to act. `AgenticCriticAgent` earns the name: it's the one piece
with an actual decision loop (§D3). Calling every pipeline stage "Agent"
regardless of whether it behaves like one is common in this space but
imprecise — worth naming correctly given how much of this document turns on
that exact distinction.

This is the **prompt chaining** workflow pattern: split a task into a
sequence of LLM calls with programmatic checkpoints in between, rather than
one large call trying to do everything. Anthropic's engineering team
documents this as the first and most reliable of five agentic workflow
patterns (prompt chaining, routing, parallelization,
orchestrator-workers, evaluator-optimizer) — reliable *because* each step is
simpler and independently checkable, at the cost of added latency.

Applied here: Detection only proposes candidates (cheap, wide net); Critic
only judges with evidence (narrow, expensive). Keeping them separate is what
lets §D3 swap the retrieval strategy under the Critic without touching
Detection at all.

**Source:** Anthropic — *"Building Effective Agents"* (Dec 2024),
anthropic.com/research/building-effective-agents

---

### D2 — Structured (AST-based) context extraction, not naive text chunking

`src/extractor/extract.clj` uses `rewrite-clj` (a real Clojure reader/zipper,
not string slicing) to pull the exact `ns` form or `defn`/`defrecord`/... form
for a candidate — never an arbitrary line-range chunk.

Repository-level code-RAG research is consistent on this point: naive
line/character chunking splits semantic units and degrades retrieval and
generation quality; structure-aware chunking (AST-based) preserves function/
declaration boundaries and is the recommended default.

**Sources:**
- cAST — *"Enhancing Code Retrieval-Augmented Generation with Structural
  Chunking via Abstract Syntax Tree"* (arXiv 2506.15655) — preprint, not
  peer-reviewed, cite with that caveat.
- *"Retrieval-Augmented Code Generation: A Survey with Focus on
  Repository-Level Approaches"* (arXiv 2510.04905) — preprint — names
  "hierarchical organization / coarse-to-fine retrieval" as a core design
  principle for production systems.

---

### D3 — Keep static RAG, add agentic tool-based retrieval as a parallel strategy

`--retrieval agentic` (default): the Critic (`AgenticCriticAgent`,
`src/agents/agentic_critic.py`) decides for itself, per candidate, whether to
call a tool for more evidence — via a LangGraph tool-calling cycle (§D11).
No embeddings, no vector DB in this path. This is the only genuinely agentic
component in the pipeline (§D1) — the default reflects that this is the
intended, recommended path, not just an alternative kept for comparison.

`--retrieval rag` (opt-in, pass explicitly): `Retriever` pre-fetches from
`ChromaVectorDBClient` (Gemini embeddings) before the Critic ever runs — one
fixed `top_k` per candidate, regardless of whether the Critic needs it.

This was driven by an explicit external prompt ("RAG is falling out of
use") that turned out to have real, current, converging evidence behind it —
both industry and peer-reviewed:

- **Anthropic removed vector search from Claude Code in May 2025**, replacing
  the embedding pipeline / local vector DB / chunking heuristics with
  agentic search (grep, glob, read, iterative). Cursor, Windsurf, Cline,
  Devin, and Sourcegraph Amp made the same move.
- **Amazon Science, AAAI 2026** (peer-reviewed): agentic keyword search
  measured at 94.5% of RAG's faithfulness with zero vector store.
- **ASE 2024** (peer-reviewed, IEEE/ACM Automated Software Engineering) —
  *"iSMELL: Assembling LLMs with Expert Toolsets for Code Smell Detection
  and Refactoring"* — dynamically routing to expert tools per smell type
  beat a plain-LLM baseline by +35 F1 points, in this exact domain.
- **PeerJ Computer Science (2026)** (peer-reviewed) — *"Pioneering agentic
  retrieval-augmented generation in software quality: a novel framework for
  code smell detection via dynamic retrieval"* — agentic RAG, DeepSeek +
  chain-of-thought, 89.5% accuracy, again in this exact domain.
- **Anthropic — "Effective Context Engineering for AI Agents"** (Sept 2025):
  formalizes "just-in-time context" — hold lightweight references, load
  data via tools at runtime — as the pattern this decision follows.

Countervailing, peer-reviewed evidence that kept this decision from going
further than it should (why RAG wasn't deleted outright):

- **EMNLP 2025** (ACL Anthology, peer-reviewed) — *"Stronger Baselines for
  Retrieval-Augmented Generation with Long-Context Language Models"* — a
  simple retrieve-then-read baseline matches or beats complex RAG pipelines
  when paired with a strong model and matched token budget. Complexity has
  to earn its keep, not be added by default.
- **ICSE 2026 Research Track** (peer-reviewed) — *"What to Retrieve for
  Effective Retrieval-Augmented Code Generation?"* — indiscriminately
  retrieved "similar code" can degrade results by up to 15%; more retrieval
  isn't automatically better.

**Net decision:** don't replace RAG, don't over-engineer the replacement
either — add agentic retrieval as a real, independently selectable second
strategy, so the two can be compared on the same pipeline rather than
argued about in the abstract.

---

### D4 — No eager index, no embeddings for the agentic path (`ExampleStore`)

`src/tools/example_lookup.py`: `__init__` does zero I/O. `get_examples()`
and `search()` glob/read the dataset fresh on every call — the smell's own
folder name (`clj-smells-dataset/smells/<category>/<smell_id>/`) *is* the
index, no separate structure to keep in sync.

This mirrors the mechanism Claude Code actually runs in production (grep +
glob + read, no pre-processing) rather than the CAG ("stuff everything into
context") alternative considered earlier — CAG doesn't scale past whatever
fits the context window, while lazy on-demand reads scale the same way
regardless of how large the rest of the dataset gets, because only what's
asked for is ever read.

**Source:** Anthropic — *"Effective Context Engineering for AI Agents"*
(Sept 2025).

---

### D5 — Progressive disclosure for reference docs (index tool + section-fetch tool)

Reference docs (`clj-smells-dataset/docs/*.md`, e.g. the Clojure style
guide) are exposed through two tools, not preloaded:
`list_doc_sections()` (cheap table of contents, ~200 tokens) and
`get_doc_section(doc, section)` (full section text, only when asked for).

This is a **three-tier discovery → activation → execution** structure — the
same shape Anthropic's own Agent Skills use for progressive disclosure (name
+ description always visible; full content loaded only on activation;
deeper resources loaded only when actually needed) — implemented here as
plain LangGraph tools rather than the Skills file format itself (see §4.1
for why).

An earlier version of this decision preloaded the full 200+ entry index into
every prompt "just in case." A real run measured it: **22,193 prompt tokens
for a single-candidate batch, and the index was never consulted.** Moving it
behind a tool call was a direct, measured correction — see §5.

Revisited 2026-08-14: briefly tried preloading just the cheap ToC (~200-300
tokens) directly into the prompt instead of behind `list_doc_sections()`, to
save one tool round-trip. Reverted — the dataset currently has one reference
doc, but this index is meant to grow, and a fixed per-run cost that scales
with however many docs get added is exactly the pattern this decision
already rejected once (§ above). A one-round-trip cost when docs are
actually needed is the safer trade as the doc set grows.

**Sources:**
- Anthropic — *"Effective Context Engineering for AI Agents"* (Sept 2025).
- SwirlAI — *"Agent Skills: Progressive Disclosure as a System Design
  Pattern"* — industry analysis, not peer-reviewed, cited for the 3-tier
  framing only.

---

### D6 — Batch tool calls; don't let the agent call one smell at a time

`get_smell_examples` takes `smell_ids: list[str]`, not a single `smell_id`.
The system prompt explicitly instructs the model to batch every smell it's
unsure about into one call.

Multi-turn tool-calling research from 2026 identifies sequential tool calls
— not retrieval volume — as the dominant cost driver in agentic RAG: each
call resends the *entire* accumulated conversation, so a 5-call session can
cost ~250K tokens against ~36K for a 3-call session covering the same
ground. Fewer, larger tool calls beat more, smaller ones, independent of how
much is actually retrieved.

Measured on this pipeline (same file, same 8 candidates, same result):
8 individual calls → 22,193 critic prompt tokens; 1 batched call → total
pipeline (Detection + Critic combined) 9,671 prompt tokens. See §5.

**Sources:**
- 2026 multi-turn tool-calling research (batch-cost finding cited above).
- Internal measurement, this repository — §5.

---

### D7 — Chain-of-Thought reasoning before the verdict, not after

Both `Critic` and `AgenticCriticAgent`'s system prompts require
`"reasoning"` to be produced *before* `"confirmed"`/`"confidence"` in the
JSON verdict, explicitly ordered in the schema and the prompt instructions.

Chain-of-thought prompting — producing intermediate reasoning steps before
a final answer — is the foundational, extensively replicated technique for
improving LLM performance on tasks requiring judgment/reasoning, vs. asking
for the answer directly.

**Source:** Wei, Wang, Schuurmans, Bosma, Ichter, Xia, Chi, Le, Zhou —
*"Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"* —
NeurIPS 2022 (peer-reviewed).

---

### D8 — Thin per-provider adapters; reuse LangChain wrappers for tool-calling, don't hand-roll it

**Superseded by §D24**, which moved the non-agentic path onto LangChain too
— the per-provider client classes named below (`OpenAIClient`,
`AnthropicClient`, etc.) no longer exist. Kept here for the historical
reasoning on *why* the agentic path used LangChain from the start; see D24
for why the split it originally justified was later closed.

`src/llm/*.py` wrap each provider's native SDK behind one `LLMClient`
interface for the non-agentic path (`complete`, `complete_structured`).

For the agentic path specifically — where tool-calling is required —
`agentic_critic.py` builds LangChain chat model wrappers
(`ChatGoogleGenerativeAI`, `ChatOpenAI`, `ChatAnthropic`, and `ChatOpenAI`
pointed at OpenRouter's/Ollama's OpenAI-compatible endpoints) bound via
`.bind_tools()`. `Orchestrator` wires the resulting model and tool list
directly into its own `StateGraph`, using `ToolNode` for execution and a
small custom routing function in place of the prebuilt `tools_condition`
(the graph needs a third destination, `finalize_agentic`, that
`tools_condition`'s two-way routing doesn't support) — see §D11.

Rationale: tool-calling wire formats differ enough per provider (OpenAI
function-calling JSON schema vs. Gemini's vs. Anthropic's) that hand-rolling
five parsers would be reinventing a solved, actively-maintained problem.
`ExampleStore`'s lookup/search/section logic is genuinely project-specific
(no library knows this dataset's folder convention) and was written by hand
for that reason — see the earlier discussion in this thread on "reinventing
the wheel": reuse the protocol layer, write the domain-specific glue.

**Source:** LangGraph/LangChain — standard, actively maintained
tool-calling and agent-graph libraries; no academic citation needed, this is
a build-vs-reuse engineering call, not a research claim.

---

### D9 — Exponential backoff with jitter for 429/503, uncapped attempts on rate limits

`src/orchestrator/retry.py`: rate-limit (429) and transient (503) errors
sleep and retry *without* consuming the `max_retries` budget; other
recoverable errors (malformed output, timeout) get capped exponential
backoff with jitter. `with_retry`'s wrapper also records `retries_used` as
an attribute so callers can report an accurate count instead of a hardcoded
value — an earlier version declared the counter but never wired it up, so
every artifact reported 0 retries regardless of what actually happened;
fixed once noticed.

Standard distributed-systems practice for talking to a shared, rate-limited
API — not a research question, no citation needed. Documented here only so
the *reason* for the split (rate limits vs. real errors) doesn't get lost.

---

### D10 — Deterministic keyword pre-filter before the Detector's LLM call

`smells_filters.json` maps a subset of `smell_id`s to "must-have" keywords
(plain substring match — e.g. `blocking_inside_go` needs `"(go "` or
`"core.async"` present somewhere in the file). `Detector.filter_catalog(code)`
runs this before building the prompt, dropping any smell whose keywords are
entirely absent from the code — those smells are structurally impossible in
this file, so there's nothing for the LLM to judge.

Not every smell has a filter entry — smells with no reliable required
keyword (e.g. `nested_forms`) are never filtered. The catalog only encodes
*sufficient-absence* conditions, not exhaustive ones, specifically to avoid
false negatives from an incomplete keyword list. This trades a small, safe,
deterministic pre-pass for a smaller Detector prompt: every dropped smell is
one fewer catalog line the Detector has to read and reason about.

**Source:** no external citation needed — a plain, project-specific
substring filter, not a research technique.

---

### D11 — One unified graph, not two

`AgenticCriticAgent`'s `agent ⇄ tools` cycle used to be its own, separately
compiled `StateGraph(MessagesState)`, invoked from a `judge_agentic` node in
`Orchestrator`'s graph — functionally correct (the cycle was still scoped to
just the Critic), but two graph objects, not one.

Merged into a single `StateGraph(PipelineState)`: `AgenticCriticAgent`
stopped owning a graph and became a plain provider of a bound model
(`llm_with_tools`), a tool list (`tools`), and prompt-building/parsing
methods (`build_initial_messages`, `extract_final_text`, `token_usage`,
`build_transcript`). `Orchestrator._build_graph()` now wires `agent` and
`tools` as literal nodes of its own graph, sharing `PipelineState` (extended
with a `messages` field, via LangGraph's `add_messages` reducer).

This also turned the Critic's malformed-output retry into a real graph
cycle (`finalize_agentic ⇄ agent`) instead of a `with_retry` decorator that
discarded the whole conversation and restarted from scratch on failure — the
new version injects a corrective message and lets the model try again with
full context of what it already did, which is both cheaper and gives the
model something concrete to correct.

**Source:** no external citation — a direct response to being asked, over
the course of building this pipeline, "why two graphs, wasn't this supposed
to be one with a cycle scoped to the critic?" Validated with mocked unit
tests (forced malformed-output retry, forced tool-call cycle) and a live
run against the real API.

---

### D12 — Anthropic prompt caching on the agentic Critic's static prefix

Per D6, every tool-call round resends the entire accumulated conversation.
The largest *static* part of that resend — the system prompt
(`AGENTIC_SYSTEM_PROMPT`, unchanged across every round) and the initial user
message (candidates + catalog descriptions, fixed once built per file) — was
being re-billed at full price on every single round even though its content
never changes within a run.

`AgenticCriticAgent.build_initial_messages()` now marks both blocks with
Anthropic's `cache_control: {"type": "ephemeral"}` when `provider ==
"anthropic"`: the system message and the initial human message are each sent
as a one-block `content` list with the breakpoint set on that block, per
Anthropic's documented mechanism (a `cache_control` breakpoint caches
everything up to and including the block it's attached to; subsequent
requests that repeat that exact prefix are served from cache at a reduced
rate instead of full price).

Scope of this change, explicitly:
- **Implemented for `provider == "anthropic"` only.** This is the one path
  where the caching mechanism (content-block `cache_control`) is directly
  under this codebase's control, well-documented, and something I could
  verify against the installed `langchain-anthropic` version rather than
  assume.
- **Not implemented for `gemini`, `openai`, or `openrouter` — researched
  2026-08-14, code change judged unnecessary there, not just unverified:**
  - **OpenAI:** automatic for prompts over a documented minimum length, no
    request changes required. This pipeline's static prefix (system prompt +
    initial candidates/catalog message) should already qualify once it's
    over that length — nothing to implement.
  - **Gemini (direct, `ChatGoogleGenerativeAI`):** "Implicit caching is
    enabled by default for all Gemini 2.5 and newer models" — fully
    automatic, ~90% discount on a cache hit, no request changes, no cache
    object to create or manage. Google's own guidance for getting hits —
    "place large and common contents at the beginning of your prompt" and
    "send requests with a similar prefix in a short amount of time" —
    describes exactly this pipeline's access pattern (static system+initial
    prompt, repeated every tool-call round, all within the same short-lived
    run). The *minimum token threshold* to trigger a hit is reported
    inconsistently across sources I checked (1,024 vs 2,048 tokens for the
    Flash tier) — not resolved here; check `ai.google.dev/gemini-api/docs/caching`
    directly before relying on an exact number. Explicit context caching
    (`cachedContent`, manually created, has a per-hour storage cost) is a
    *separate* mechanism from implicit caching and a poor fit for this
    pipeline regardless — it pays off for large context reused across many
    independent requests, not a single short multi-turn conversation like
    ours; not pursued.
  - **OpenRouter:** per OpenRouter's own docs, caching behavior depends on
    which model a request routes to, not on OpenRouter itself: OpenAI,
    DeepSeek, Groq, Grok, Moonshot, Z.AI, and **Gemini 2.5** models are
    cached automatically, no request changes; **Anthropic Claude, Alibaba
    Qwen, and non-2.5 Gemini** models require the same explicit
    `cache_control` content-block breakpoints as direct Anthropic. The
    critic's actual observed model in this repo's runs (`gemini-flash-latest`
    via `openrouter`, per `results/Arcadia/.../sequences.clj_result.json`)
    falls in the automatic-Gemini-2.5 bucket — already covered, no code
    change needed for that specific case. The one real gap: this pipeline's
    `openrouter` provider path uses `ChatOpenAI` pointed at OpenRouter's
    OpenAI-compatible endpoint (D8), and it's untested whether LangChain's
    `ChatOpenAI` content-block schema passes an injected `cache_control` key
    through to OpenRouter for the Anthropic-via-OpenRouter case — left
    unimplemented rather than shipped unverified.
  - **Ollama:** local inference, no provider-side token billing — caching in
    the sense this decision means (reducing $ cost of repeated tokens)
    doesn't apply.
- Tool schemas (5 tool definitions, resent on every round via
  `bind_tools()`) are **not** cached by this change, on any provider.
  Anthropic also supports a cache breakpoint on the tools array, but doing
  that cleanly means constructing raw tool schemas with an embedded
  `cache_control` field instead of relying on LangChain's `@tool` →
  `bind_tools()` conversion. Left as a follow-up rather than implemented
  against unverified internals.

No before/after token measurement has been taken on this repo yet for any
provider — unlike D5/D6, this decision rests on providers' documented
caching behavior, not a locally measured result. Treat "reduces cost" as:
true if each provider's documented mechanism works as documented, not yet
confirmed by a run of this pipeline.

**Sources:**
- Anthropic — official prompt caching documentation (`cache_control`
  breakpoints on system/tools/message content blocks; direct-API-only
  mechanism, distinct from how e.g. Bedrock handles it) — the specific
  mechanism this change implements.
- OpenAI — official prompt caching documentation (automatic for prompts
  above a minimum length, applied to a repeated prefix, no code required) —
  cited only for why no code change was made on that path, not independently
  verified against this pipeline's actual traffic.
- Google — *"Context caching | Gemini API"*, ai.google.dev/gemini-api/docs/caching
  (implicit caching default-on for Gemini 2.5+, ~90% discount, no request
  changes; cache-hit tips; minimum token threshold reported inconsistently
  across sources, flagged above rather than asserted as one number).
- OpenRouter — *"Prompt Caching"*, openrouter.ai/docs/guides/best-practices/prompt-caching
  (per-provider automatic vs. explicit-breakpoint split, request formats,
  pricing table, minimum token thresholds, sticky-routing/`session_id`
  behavior for multi-turn caching).
- `langchain-anthropic` 1.5.6 (installed in `.venv`) — inspected directly
  (`_get_request_payload` / `_apply_cache_control_to_last_eligible_block` in
  `langchain_anthropic/chat_models.py`) to confirm the direct-Anthropic
  content-block mechanism this change relies on, rather than assuming API
  shape from memory.

---

### D13 — Prompt caching for the OpenRouter path (`provider == "openrouter"`)

D12 covered `provider == "anthropic"` only, leaving OpenRouter — this
project's actual default in practice (every result under `results/` was run
with `--provider openrouter --model gemini-flash-latest`, per
`sequences.clj_result.json`'s `agents.detection.model`) — unimplemented.
Researched and implemented 2026-08-14.

**Message ordering:** already prefix-stable, no change needed. Per D1/D11,
`Orchestrator._build_graph()`'s `messages` field is populated once by
`_node_prepare_agentic` (system prompt, then the initial candidates+catalog
message — both fixed for the whole run) and only ever *appended to*
afterward, by `_node_agent` (AI response) and the `tools` `ToolNode` (tool
results), via LangGraph's `add_messages` reducer. Nothing reorders or
rewrites earlier messages. `self.tools` (bound via `bind_tools()` in
`AgenticCriticAgent.__init__`) is built once per critic instance and reused
across every round and every file in a batch run, so the tool-schema portion
of the request is also already identical call to call.

**What was implemented, in `src/agents/agentic_critic.py` and
`src/orchestrator/orchestrator.py`:**

1. **Static-prefix breakpoint** — `build_initial_messages()` gained an
   `elif self.provider == "openrouter"` branch (parallel to D12's Anthropic
   one) marking the system message and the initial human message with
   OpenRouter's explicit-caching field, `prompt_cache_breakpoint: {"mode":
   "explicit"}`, on their text content block.
2. **Moving breakpoint on the growing tail** — a new
   `AgenticCriticAgent.with_cache_breakpoint(messages)` marks the *last*
   message in the list (the most recently appended tool result, or the
   initial message on round 1) with the same field, on a copy — the
   original `PipelineState["messages"]` history is never mutated, only the
   list handed to `.invoke()` for that one call. `Orchestrator._node_agent`
   calls this immediately before invoking the model. This is what makes
   round N's call reuse everything cached through round N-1 and pay full
   price only for what's newly appended — the exact mechanism the user's
   own worked example (SYSTEM/TOOLS/CONTEXTO, then +TOOL_CALL_A/RESULTADO_A,
   then +TOOL_CALL_B/RESULTADO_B) describes. Tool result history itself is
   never trimmed or summarized to make this work — only requested change
   was where the cache marker sits, not what's kept. **Not** called from
   `_node_force_finalize` — see the dedicated note below.
3. **`session_id`** — `AgenticCriticAgent.reset_run()` now takes a `run_id`
   (the same id `Orchestrator.run()` generates once per file and reuses for
   that run's `RunArtifact.run_id`) and derives `self.session_id =
   f"critic-agent-{run_id}"` from it, stored for the run's lifetime. Sent on
   every call via `invoke_kwargs()` → `extra_body={"session_id": ...}` — the
   documented `ChatOpenAI` mechanism for provider-specific fields on
   OpenAI-compatible transports, whose own docstring names OpenRouter
   explicitly. This matches OpenRouter's documented sticky-routing feature,
   which uses `session_id` to keep every call for the same run on the same
   upstream provider endpoint within its cache TTL window, rather than
   risking a fresh, uncached endpoint on any given round.
4. **Observability** — `Orchestrator._log_cache_usage()` logs
   `prompt_tokens` / `cached_tokens` / `cache_write_tokens` (read from
   `AIMessage.usage_metadata["input_token_details"]["cache_read"]` /
   `["cache_creation"]`) after every `agent` and `force_finalize` call, so
   cache hits are checked from real API responses, not assumed from the
   request shape being "correct."

**`_node_force_finalize` deliberately does NOT mark a cache breakpoint —
found and fixed 2026-08-14, from a live run's own logged numbers.** A real
run against `server.clj` (`--critic-model anthropic/claude-sonnet-5`) hit
`Orchestrator`'s tool-call round budget (the `tool_rounds` counter /
`_route_agent` → `force_finalize` mechanism, added earlier in this
project's history to replace a hard `GraphRecursionError` crash with a
graceful forced answer — not itself a numbered decision in this log, just
existing graph behavior). The run logged 6 tool-call rounds climbing to a
99% cache-hit rate, then the `force_finalize` call logging
`cached_tokens=0` — a full miss — despite `session_id` being identical
across every call in the run. Cause: `force_finalize` invokes
`self.critic._llm` (tools unbound — deliberately, so the model is
structurally unable to request yet another tool call once the round budget
is spent), not `self.critic.llm_with_tools`. The tools array is itself part
of what a provider's cache key is computed over, so removing it changes the
request's effective prefix even though the system prompt and message text
are byte-identical — the 6 rounds' cache can never be read from this
differently-shaped request. Worse, since this is the run's last call, a
breakpoint here would pay the cache-*write* premium (documented ~1.25x for
Anthropic's 5-minute-TTL default, per the OpenRouter pricing table cited in
D12/D13's sources) for content nothing will ever read back — measured on
that run as ~1,747 token-cost-equivalent wasted, ~3.8% of that file's total
critic prompt tokens. Fix: stopped calling `with_cache_breakpoint()` before
this one call. Kept the tools-unbound design as-is — that guarantee
(deterministic termination once the round budget is spent) is worth more
than the small cache-reuse cost it forgoes; not revisited here, just
stopped paying an extra premium on top of it.

**Field choice — why `prompt_cache_breakpoint`, not `cache_control`, for
this path:** OpenRouter's docs show both an Anthropic-style `cache_control`
format and an OpenAI-style `prompt_cache_breakpoint` format, and state
OpenRouter converts between them depending on the underlying routed model
("Block Interoperability: Anthropic `cache_control` converts to
`prompt_cache_breakpoint` for OpenAI routing, and vice versa"). This
project's `openrouter` provider path uses `ChatOpenAI` (D8) over the
OpenAI-compatible transport, not `ChatAnthropic` — so which field actually
survives serialization is a property of the installed `langchain-openai`
library, not a free choice. Read directly from the installed version
(`langchain-openai` 1.5.0, `langchain_openai/chat_models/base.py`):
`_format_message_content()` preserves `prompt_cache_breakpoint` on any
message's text block (confirmed by reading `_apply_prompt_cache_breakpoint`
and the general dict-passthrough fallback it falls into otherwise), but
`_sanitize_chat_completions_content()` — applied specifically to
`ToolMessage` content — strips every key off a text block *except*
`type`/`text`/`prompt_cache_breakpoint`. A `cache_control` key would
therefore silently survive on system/human/AI messages but be dropped on
tool-result messages specifically — and tool results are exactly the
content `with_cache_breakpoint()` needs to mark most often, since they're
what the "moving breakpoint on the tail" strategy marks on every round past
the first. `prompt_cache_breakpoint` was confirmed (see below) to survive
all three message types actually used here; `cache_control` was not
re-verified for the tool-message case given this asymmetry, to avoid
shipping something that works in 3 of 4 message types and fails silently on
the 4th.

**Verified, not assumed** — before writing any of the above, ran (not just
read) the actual conversion code in this repo's own `.venv`:
- `ChatOpenAI._get_request_payload()` on hand-built messages carrying
  `prompt_cache_breakpoint` blocks and an `extra_body={"session_id": ...}`
  kwarg, confirming the final JSON payload has `session_id` as a top-level
  key and `prompt_cache_breakpoint` intact on every message's content block.
- `_convert_message_to_dict()` on a `ToolMessage` specifically, confirming
  `prompt_cache_breakpoint` survives `_sanitize_chat_completions_content`
  unmodified (the one path that strips other unrecognized keys).
- `AgenticCriticAgent.with_cache_breakpoint()` against real
  `langchain_core` message objects, confirming it returns a new list
  (original `PipelineState` messages left unmutated) with only the tail
  message's content changed.
- `Orchestrator._log_cache_usage()` against both a synthetic `AIMessage`
  with `usage_metadata` set and one without, confirming it logs cache-hit
  percentages in the first case and reports "no usage_metadata" rather than
  crashing in the second.

**Not done, on purpose, per explicit scope:**
- No history summarization/trimming — the full tool-result history is still
  sent every round; only where the cache breakpoint sits changed.
- No response/result caching — every call still gets a real model response;
  only the *input* prefix is what's reused.
- No change to agent decision logic or tool behavior.
- Tool-schema caching (the 5 tool definitions themselves) — same gap D12
  already flagged for Anthropic, and unaddressed here for the same reason
  (would need to bypass `bind_tools()`'s schema construction).
- No before/after token measurement on a live run yet — the payload
  shape and field survival are verified against the installed library
  directly; whether OpenRouter's cache actually hits at the rates its docs
  describe, for the models this project actually uses, is not yet confirmed
  by a live run's logged `cached_tokens`.

**Sources:**
- OpenRouter — *"Prompt Caching"*, openrouter.ai/docs/guides/best-practices/prompt-caching
  (per-provider automatic vs. explicit format, `prompt_cache_breakpoint`
  request shape, `session_id` sticky-routing behavior, `cache_control` ⇄
  `prompt_cache_breakpoint` interoperability, `usage.prompt_tokens_details`
  response fields this decision's observability logging reads from).
- `langchain-openai` 1.5.0 (installed in `.venv`) — inspected and exercised
  directly (`_format_message_content`, `_sanitize_chat_completions_content`,
  `_apply_prompt_cache_breakpoint`, `_get_request_payload`,
  `ChatOpenAI.extra_body` docstring which names OpenRouter explicitly, and
  the usage-parsing code populating `usage_metadata["input_token_details"]`
  from `prompt_tokens_details.cached_tokens`/`cache_write_tokens`) in
  `langchain_openai/chat_models/base.py`, rather than assuming API shape.
- `results/Arcadia/Source/clojure/test_clojure/sequences.clj_result.json` —
  this repository's own evidence that `openrouter` is the provider actually
  used in practice, not a hypothetical path.

---

### D14 — Removed `search_dataset`; `get_smell_examples` is the only code-evidence tool

The Critic went from five tools to four: `get_smell_examples`,
`list_doc_sections`, `get_doc_section`, `get_function_source`.
`search_dataset` (free-text/regex search across the dataset, for when the
agent didn't already know a smell_id) is gone — `ExampleStore.search()`,
`_docs_matches()`, `_excerpt()`, and `format_search_results()` were deleted
outright, not deprecated in place.

**Why, in order of how this was actually reasoned through:**

1. `search_dataset`'s JSONL branch originally searched all 839 records in
   `exports/rag_chunks_draft.jsonl` with no curation filter — 763 of them
   `pending` (an unreviewed LLM guess, `llm_suggested_reasoning`, never seen
   by a human) against only 76 `confirmed`. A live trace
   (`results/test_clojure/server.clj_trace.md`, 2026-08-14) showed the tool
   surfacing two `pending` examples as if they were precedent, with no
   verdict or reasoning attached — code-only snippets the critic couldn't
   actually weigh. First fix: filtered `search()` to `confirmed`-only,
   matching `_real_curated_examples()`'s existing policy, and started
   rendering `smell_verdict` + `final_reasoning` in both this tool's output
   and `get_smell_examples`'s (`CodeExample.description` was already being
   fetched but silently dropped by `format_example()` before this).
2. That fix made `search_dataset` correct, but exposed that it was now
   largely redundant with `get_smell_examples` for this critic's actual
   usage pattern: every candidate arrives from Detection with its
   `smell_id` already known, so the "I don't know which smell_id fits"
   case `search_dataset` exists for essentially never applies here — as
   confirmed by re-reading every trace referenced in this document, where
   `search_dataset` was only ever observed being used to re-fetch examples
   for a smell_id the critic already had (the exact anti-pattern its own
   docstring told it not to do), never for genuine smell-id disambiguation.
3. Doc-content keyword search — `search_dataset`'s one capability
   `get_smell_examples` never had — was judged not worth keeping a whole
   tool for on its own, given `list_doc_sections()` + `get_doc_section()`
   already cover the docs use case by section/heading.

Net effect on the tool-call cost problem this document already tracks (D6,
D13): one fewer tool schema resent on every round, and one fewer plausible
"let me just check" detour like the ones in the `server.clj` trace (turns
2/3/4/5 there were largely `search_dataset` calls re-covering ground
`get_smell_examples` already had, or fishing with no real target).

**Source:** this repository's own dataset composition (839/763/76 counts
above, `/Users/walber.filho.nufuturo/clj-smells-dataset/exports/rag_chunks_draft.jsonl`,
counted directly rather than assumed) and `server.clj`'s trace/result —
not an external citation; a design call made and verified in-session, per
the user's explicit instruction to rely only on curated evidence.

---

### D15 — No `temperature` on direct-Anthropic calls; larger `max_tokens` in `AnthropicClient`

`AgenticCriticAgent.build_chat_model()`'s `provider == "anthropic"` branch
and `src/llm/anthropic_client.py`'s `AnthropicClient.complete()` both used
to pass `temperature=0` straight to Anthropic — the former via
`ChatAnthropic(..., temperature=0)`, the latter via the raw `anthropic`
Python SDK's `messages.create(..., temperature=0, max_tokens=4096)`.

Anthropic's own current prompting docs state that setting
`temperature`/`top_p`/`top_k` to a non-default value **returns a 400 error
on Claude Sonnet 5** — a constraint that didn't exist for older Sonnet
models this same code path also supports. `temperature=0` is a non-default
value (the API's own default is `1`), so any run pointed at
`claude-sonnet-5` through either of these two direct-Anthropic paths would
fail outright. Fixed by simply not passing `temperature` for Anthropic —
per the same docs' own migration guidance ("remove these parameters... use
system-prompt instructions to guide behavior instead"), not by trying to
find a value that happens to still work.

Also bumped `AnthropicClient`'s `max_tokens` from 4096 to 8192, per the
same docs' separate warning: on models with adaptive thinking on by default
(Claude Sonnet 5 is one), thinking and the response text share the
`max_tokens` budget, so a tight cap can produce a response that's almost
entirely thinking, truncated before the actual output. 8192 is a
conservative headroom increase, not a benchmarked "correct" number — the
docs don't give one.

**Scope check, so this isn't overclaimed:** this was NOT triggered by
anything actually observed failing — every run referenced elsewhere in this
document used `provider == "openrouter"` (`ChatOpenAI` pointed at
OpenRouter's endpoint), not `provider == "anthropic"` directly, and those
runs completed successfully with `temperature=0` still in place on that
path. This fix targets the direct-Anthropic path specifically, on the
strength of Anthropic's own documented behavior for it, not an observed
failure — flagged as unverified-by-runtime, verified-by-source. The
`openrouter`/`ollama`/`openai`/`gemini` branches in the same function were
deliberately left untouched: I have no equivalent source-backed claim about
them, and for `openrouter` specifically I have direct counter-evidence
(successful runs) that whatever OpenRouter does with `temperature=0` before
forwarding to Anthropic doesn't reproduce this error.

**Sources:**
- Anthropic — *"Prompting Claude Sonnet 5"*,
  platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5
  ("Tone and writing style": non-default `temperature`/`top_p`/`top_k`
  returns a 400 error on Claude Sonnet 5) and *"Prompting best practices"*,
  platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
  (adaptive thinking sharing the `max_tokens` budget with response text).
- `langchain-anthropic` 1.5.6 (installed in `.venv`) — inspected directly
  (`set_default_max_tokens` validator in `ChatAnthropic`) to confirm the
  LangChain path already derives a model-aware `max_tokens` fallback when
  none is given, so no equivalent fix was needed there — only the raw-SDK
  `AnthropicClient` has a hardcoded value.

---

### D16 — Prompt structure brought in line with current cross-provider guidance (XML sections, few-shot examples)

Requested explicitly as a cross-provider check, not a Claude-specific tune:
this pipeline runs `--critic-model` and `--detection-model` against
whichever provider is configured (`gemini`, `openai`, `anthropic`,
`openrouter`, `ollama`), and the user is actively switching between them —
so a prompt change justified only by Claude's docs isn't good enough here.
Researched Anthropic's, OpenAI's, and Google's own current prompting
guidance independently and only acted on what all three agreed on.

**What all three sources say, independently:**
- **Structure prompts with tags/headers.** Anthropic: "XML tags help Claude
  parse complex prompts unambiguously... wrapping each type of content in
  its own tag... reduces misinterpretation." OpenAI: "Markdown headers and
  lists can be helpful to mark distinct sections of a prompt," recommends
  organizing as Identity → Instructions → Examples → Context. Google:
  recommends XML-style tags OR Markdown headings, "choose one format
  consistently within a single prompt."
- **Include few-shot examples.** Anthropic: "3–5 examples for best
  results," wrapped in `<example>` tags. OpenAI: lists "Examples" as one of
  the four standard sections of a well-structured prompt. Google, most
  bluntly: "We recommend to always include few-shot examples in your
  prompts. Prompts without few-shot examples are likely to be less
  effective."
- **Say what to do, not what not to do.** Anthropic gives this as an
  explicit output-formatting tactic ("Tell Claude what to do instead of
  what not to do").

**What changed**, in `SYSTEM_PROMPT` in both `src/agents/agentic_critic.py`
and `src/agents/critic.py` (kept in sync, same structure in both — see
D-log convention elsewhere in this document of mirroring prompt shape
across the agentic and rag-mode critics):
1. Wrapped the existing sections in `<role>`, `<context>`, `<tools>` /
   `<tool_use_guidelines>` (agentic only), `<output_format>`, and
   `<confidence_rubric>` tags. No instructional content was removed or
   reworded in this step — purely a structural wrap.
2. Added an `<examples>` block with 3 worked, clearly-labeled-illustrative
   verdicts (not drawn from any real file, to avoid overfitting toward this
   project's actual candidate set) — one per confidence tier from the
   rubric added in the previous session (`high` / `medium` with a named
   contextual factor / `low`), so the rubric is demonstrated, not just
   stated. Each example's JSON was validated with `json.loads()` before
   committing — an example teaching malformed JSON would be worse than no
   example.
3. Fixed a real, separate bug this pass surfaced: the agentic
   `SYSTEM_PROMPT`'s tool section had drifted out of sync with
   `get_smell_examples`'s own tool docstring — the system prompt still said
   calling it again for a known smell_id "returns the exact same thing —
   don't," while the tool's actual (already-updated, in an earlier session)
   behavior returns the next not-yet-seen batch or a "no more" notice. The
   model was receiving two contradictory descriptions of the same tool
   (system prompt text is fixed at conversation start; the tool's own
   description is resent from its schema every round) — plausibly part of
   why a live trace showed the model calling `get_smell_examples` with an
   empty `smell_ids` list (see the fix for that in the same session,
   `agentic_critic.py`'s empty-input guards). Fixed by no longer
   paraphrasing tool mechanics in the system prompt at all — the
   `<tools>` section now only states *when* to reach for each tool, and
   defers to "each tool's own description covers exactly what it returns,"
   removing the second, driftable copy of the same information.

**Not done:** did not restructure the per-call *user* prompt (candidates +
catalog descriptions, built in `build_initial_messages()`) — it already
uses consistent Markdown `##` headers, which is one of the three sources'
explicitly endorsed formats, so the marginal gain was judged not worth
touching a part of the prompt the caching mechanism (D12/D13) is tuned
around.

**Sources:**
- Anthropic — *"Prompting best practices"*,
  platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
  (XML tag structuring, example count/format, positive-instruction framing).
- OpenAI — *"Prompt engineering"*, developers.openai.com/api/docs/guides/prompt-engineering
  (Identity/Instructions/Examples/Context structure, Markdown/XML section
  delimiters).
- Google — *"Prompt design strategies"*, ai.google.dev/gemini-api/docs/prompting-strategies
  (few-shot-examples recommendation, XML/Markdown delimiter guidance).

---

### D17 — Cache observability and explicit marking outside the agentic Critic (Detection, rag-mode Critic)

D12/D13 only instrumented and marked the agentic Critic's OpenRouter calls.
Prompted by the user noticing, from a real batch-run log, that round-1
`cached_tokens` on the Critic was identical (3407) across every file in the
run — meaning the Critic's system prompt was already being read from cache
*across files*, not just across tool-call rounds within one file — and then
asking whether the same should apply to "the first LLM" (Detection), which
also has a `SYSTEM_PROMPT` that's byte-identical across every file in a
batch. It didn't: Detection goes through `src/llm/*.py`'s `LLMClient`
abstraction (D8) — a thin wrapper around each provider's own SDK, not
LangChain — and none of those clients read or marked anything cache-related
before this.

**Observability (all providers going through the `openai` SDK shape):**
`LLMResponse` (`src/llm/base.py`) gained `cache_read_tokens`/
`cache_write_tokens` fields (default 0), and a shared
`cache_tokens_from_openai_usage(usage)` helper reads them from
`usage.prompt_tokens_details.cached_tokens`/`.cache_write_tokens` — the same
field names D13 already verified against the `openai` Python SDK's own
`PromptTokensDetails` type (re-confirmed here:
`openai.types.completion_usage.PromptTokensDetails`, installed in `.venv`).
Wired into `OpenRouterClient` and `OpenAIClient` (both `complete()` and
`complete_structured()`) — not `AnthropicClient`/`GeminiClient`/
`OllamaClient`, whose response shapes weren't researched for this. Plumbed
through to `AgentLLMMetrics.cache_read_tokens`/`cache_write_tokens` for the
`detection` agent in `Orchestrator.run()` (the `critic` agent's version was
already wired in D13), and logged per-file via a new
`[Detection][cache] prompt_tokens=... cached_tokens=... cache_write_tokens=...`
line, mirroring the existing `[AgenticCritic][cache]` one — only when there's
something nonzero to report, so files run through a provider this project
doesn't instrument for cache (Gemini/Anthropic/Ollama direct) don't print a
misleading "0% cached" that looks like a negative result rather than an
unmeasured one.

**Explicit marking, gated on `--dir` — the part actually requested.**
`OpenRouterClient` gained a `use_prompt_cache: bool = False` constructor
flag; when `True`, `complete()`/`complete_structured()` send the system
message as a `prompt_cache_breakpoint`-marked content block (D13's format,
the constant moved to `src/llm/base.py` as `OPENROUTER_CACHE_BREAKPOINT` so
`agentic_critic.py` and this file share one literal instead of two that can
drift). Default `False` — matching the same reasoning as
`_node_force_finalize`'s D13 fix: this client is single-shot per call (no
growing multi-round conversation the way the agentic Critic has), so the
*only* thing a breakpoint here could ever pay off on is a *later, separate*
`complete()` call with the same `system` text — which only happens when the
same `Detector`/`Critic` instance is reused across multiple files, i.e.
`--dir` (directory/batch mode). On a single file, marking would pay the
cache-write premium for a write nothing will ever read back. `main.py` wires
`use_prompt_cache=args.dir` into both `_build_llm()` calls (`detection_llm`
and, for `--retrieval rag`, `critic_llm` — same reasoning applies to
`critic.py`'s D16-restructured `SYSTEM_PROMPT`, also constant across files).
Only `OpenRouterClient` takes this parameter — `_build_llm()`'s other
branches don't, since D13's explicit-vs-automatic research was specific to
OpenRouter's transport.

**Batch-level total.** Per-file `cache_read_tokens`/`cache_write_tokens`
already existed (nested under each file's own `agents.detection`/
`agents.critic`) but had no cross-file total anywhere — asked directly:
"o JSON de saída está mostrando o total de token que foi reaproveitado por
cache... além do total gasto que já mostra?" It wasn't. `write_summary_json()`
(`src/utils/io.py`) gained `total_cache_read_tokens`/`total_cache_write_tokens`
parameters, summed in `main.py`'s `process_file()` across both agents for
every file, written into the batch `summary_*.json`'s `"tokens"` object as
`cache_read`/`cache_write` alongside the existing `prompt`/`completion`/
`total`, and logged as a `Total Cache: N read, M written (X% ...)` line at
the end of a run (only when nonzero, same reasoning as the per-file log).

**Verified, not assumed** — same discipline as D12/D13: ran the actual code
in this repo's `.venv` before writing any of it. `cache_tokens_from_openai_usage`
tested against real `openai.types.completion_usage.CompletionUsage`/
`PromptTokensDetails` instances, with and without the details block present.
`OpenRouterClient._system_message()` checked to confirm `use_prompt_cache=False`
produces the original plain-string message (no behavior change for anyone
not opting in) and `use_prompt_cache=True` produces the marked block.
`write_summary_json()` run end-to-end against a temp directory, output JSON
inspected to confirm the new `cache_read`/`cache_write` keys land correctly
next to the existing token totals.

**Sources:**
- OpenRouter — *"Prompt Caching"*, openrouter.ai/docs/guides/best-practices/prompt-caching
  (same citation as D13 — `prompt_cache_breakpoint` format, automatic vs.
  explicit caching per underlying model).
- `openai` Python SDK (installed in `.venv`) — `openai.types.completion_usage.PromptTokensDetails`
  inspected directly to confirm `cached_tokens`/`cache_write_tokens` field
  names, rather than assuming they match D13's LangChain-side findings.
- This repository's own batch-run log (`server.clj`/`transducers.clj`/.../
  `arcadia_tests.clj`, 2026-08-14) — the repeated `cached_tokens=3407` across
  seven different files' round-1 calls is what surfaced that cross-file
  caching was already happening for the Critic, prompting this decision for
  Detection.

---

### D18 — `get_doc_section` matching made robust to how `list_doc_sections()` displays entries; two more no-resend guards

From `results/pedestal/build/build.clj_trace.md` (2026-08-14) — a single,
unambiguous candidate (`single_segment_namespace` on `(ns build ...)`) that
took 5 tool calls and 7 turns to resolve. Three real findings, all verified
against the actual trace and the actual code before changing anything:

1. **`get_doc_section` failed on a section name that should have worked.**
   Turn 3 called `get_doc_section({'doc': 'clojure-style-guide.md',
   'section': 'No Single Segment Namespaces [no-single-segment-namespaces]'})`
   — the exact text of `list_doc_sections()`'s displayed bullet line for
   that entry — and got "No section matching...". Turn 4 retried with just
   `'no-single-segment-namespaces'` and succeeded. Root cause, confirmed by
   reading `get_doc_section()`: it matches `section` against `title` or
   `anchor` with exact equality; `format_doc_index()` renders each entry as
   one line, `"{title} [{anchor}]"`, and the model pasted that whole
   displayed line back rather than extracting just the anchor. The same
   pattern (title+bracket pasted whole, retried correctly one turn later)
   also appears in an earlier trace referenced elsewhere in this document
   (`server.clj`) — two independent occurrences, not a one-off. Fixed in
   `ExampleStore.get_doc_section()`: if `section` ends in a `[...]`
   bracket, also try the bracket content and the pre-bracket text as
   fallback matches before giving up. Verified against the exact failing
   string from the trace — now resolves on the first try.
2. **`list_doc_sections()` was called twice in one conversation** (turns 2
   and 5) with nothing having changed in between — a full resend of a
   ~2,408-token index for zero new information. Fixed the same way D14
   fixed repeat `get_smell_examples` calls: `AgenticCriticAgent` tracks
   whether the index was already sent this run (`self._doc_index_sent`,
   reset in `reset_run()`) and returns a short "already have it, nothing
   changed" notice instead of resending on a repeat call.
3. **Investigated but did NOT act on: is the index too large?** Measured
   directly: 212 headings across the one indexed doc, ~2,408 tokens — over
   10x D5's original ~200-token estimate for this table of contents.
   Breaking down by heading level: 162 of 212 (76%) are level-3 headings —
   including both entries any trace has actually asked for successfully
   (`no-single-segment-namespaces`, `prefer-require-over-use`, both level-3
   under "Namespace Declaration"). Measured the alternative before
   proposing it: fetching the level-2 parent "Namespace Declaration" whole
   (what the agent would be pushed toward if level-3 entries were dropped
   from the index) costs **1,887 tokens on its own** — almost as much as
   the entire current index — for one section instead of the whole
   catalog. Trimming the index would trade "large table of contents, fetch
   exactly what's needed" for "smaller table of contents, but each fetch
   pulls in far more than needed" — not a clear win, so left unchanged.
   This should be revisited if the docs set grows enough that level-3
   granularity stops being roughly this cheap per section.
4. **Fixed a stale docstring**, found while reading this code for (1)/(2):
   `ExampleStore.list_doc_sections()`'s docstring still said "meant to be
   preloaded once per run... not fetched via a tool call" — left over from
   the preload experiment tried and reverted earlier in this document
   (D5's revision note). Updated to describe the actual current, reverted-
   to design instead of the abandoned one.

**What this didn't change:** the final verdict itself was good —
`confirmed: true, confidence: medium`, correctly citing the style guide's
"in your own private app... do whatever you like" carve-out and applying it
specifically because `build.clj` is a private build script, not a
published library. The slowness was entirely in the path to that verdict,
not the reasoning quality once there — this decision is about the path,
not a correctness fix.

**Source:** `results/pedestal/build/build.clj_trace.md` and direct
measurement against `clj-smells-dataset/docs/clojure-style-guide.md` and
`ExampleStore` — not an external citation; the bug and its fix are both
this repository's own code and data.

---

### D19 — `get_doc_section` batches multiple sections; round-cap left alone

Prompted by asking whether D12/D13/D17's caching made it worth raising
`max_tool_rounds` (currently 6) so the Critic could "navigate the index"
more freely. Discussed before touching anything, per explicit instruction.

**Why the round cap wasn't raised:**
- Caching lowers the *marginal $ cost* of a later round (rounds 4-6 in
  observed traces run 68-99% cache-hit), but does nothing for *latency* —
  each round is still a full network round-trip plus model thinking time;
  observed rounds in this repo's traces run 2-20 seconds each, and 5-6
  round files already took 40-90 seconds end to end in a batch run. A
  higher cap raises the worst-case wall-clock per file, which compounds
  across a directory of hundreds of files — caching doesn't touch that
  axis at all.
- The round cap is also the safety valve from the earlier
  `GraphRecursionError` fix (§ this document, `force_finalize`/
  `tool_rounds`): it bounds the blast radius of a file where the model gets
  stuck. Raising it raises that bound too, in time if not in $.
- The concrete waste actually observed in `build.clj`'s trace (D18: a
  failed section lookup, a duplicate index fetch) wasn't a round-budget
  problem — it was fixed directly in D18. The same 6-round budget should
  reach further now that those specific rounds aren't being burned on
  retries and duplicates it should never have needed.

**What was done instead:** `get_doc_section` changed from `(doc, section)`
— one section per call — to `(doc, sections: list[str])`, matching the
batching pattern `get_smell_examples`/`get_function_source` already use.
"Navigating the index" (looking at several sections to answer one
style/idiom question) no longer costs one round per section; it costs one
round for as many sections as the model wants from a given doc, batched.
This gets the exploration `max_tool_rounds` was proposed to enable, without
its downside — no change to worst-case time or the safety-valve bound.
Verified against the exact two sections referenced in D18's trace
(`no-single-segment-namespaces`, `prefer-require-over-use`), fetched
together in one call, plus the empty-list case returning a message instead
of silently succeeding with nothing (same reasoning as D17's empty-input
guards on the other two batchable tools).

**Left open, not decided against:** a modest bump to `max_tool_rounds`
(e.g. 6→8) as a secondary, smaller lever, only worth revisiting after
re-measuring whether D18+this decision's fixes already resolve the
original complaint on a fresh run.

**Source:** this conversation's own discussion and the trace/measurements
D18 already cites — not an external citation, a design call weighing the
tradeoffs above before implementing, per explicit instruction to discuss
first.

---

### D20 — Catalog description deduped per unique smell_id (agentic path)

Found from a real trace: when the same `smell_id` is flagged on multiple
elements in one file (e.g. `relying_on_load_time_side_effects` on three
different `def`s), `AgenticCriticAgent.build_initial_messages()`'s "##
Catalog Descriptions" section repeated that smell's full name+summary once
per *candidate*, not once per unique smell_id — three occurrences of the
same paragraph for three candidates sharing one smell_id, pure duplication
with zero new information.

Fixed by tracking `seen_smell_ids` while building `catalog_parts`, skipping
a smell_id already added. `src/agents/critic.py` (rag mode) already did
this correctly — its `run()` has explicit "Group evidence by unique
smell_id to avoid repeating tokens" logic — so this bug was specific to the
agentic path; the rag-mode Critic needed no change. Verified with three
candidates sharing one smell_id: the catalog description now appears
exactly once in the built prompt instead of three times.

**Source:** user-reported, directly from a real run's prompt output
(candidate smells list with a repeated smell_id) — not an external
citation.

---

### D21 — `get_function_source` recognizes when the file was already given in full

User-reported from a real tool-call transcript: the Critic called
`get_function_source(['read-config'])` for a candidate whose file-scope
context had *already* embedded the entire file (the `__FILE_SCOPE__` /
"All Candidates (full file provided...)" branch of
`build_initial_messages()`, used when candidate context extraction falls
back to file-level scope — see `SMELL_SCOPE` in `orchestrator.py`).
`read-config` was defined in that same file, so its source was already
sitting in the conversation — the tool call re-extracted and re-sent code
the model already had, for nothing.

Two-part fix, belt-and-suspenders rather than relying on either alone:
1. **Told the model directly.** When `build_initial_messages()` takes the
   file-scope branch, the full-file block now ends with a note: everything
   defined in this file is already visible, `get_function_source` is only
   for functions defined elsewhere.
2. **Made the tool itself recognize it**, in case the model calls it
   anyway (docstrings and prompt notes get missed — D18 already found two
   cases of that in this same tool family). `AgenticCriticAgent` now tracks
   `self._file_shown_in_full` (set in `build_initial_messages()` from the
   same `has_file_scope` check already computed there, reset per run in
   `reset_run()`). `get_function_source` checks it before running the
   `bb`/`extract.clj` subprocess: if the function resolves to the *current*
   file and the full file was already shown, it skips extraction entirely
   and returns a one-line pointer back to the file already in context —
   saving both the subprocess call and the re-sent tokens, not just the
   tokens.

Verified end to end: built a temp file, ran `build_initial_messages()`
through the real file-scope path, confirmed `_file_shown_in_full` is set,
then called the actual tool and confirmed it returns the short pointer
without invoking `bb` at all (no extraction subprocess run).

**Source:** user-reported, from a real tool-calling transcript — not an
external citation.

---

### D22 — Progress count on `get_smell_examples`; `_POSITIVE_EXAMPLES_CAP` 2→3; `get_function_source` warned off core-language names

From two real traces (Pedestal `Pedestal`/`Greeter` components, both
`map_with_nil_values` candidates on `defrecord` lifecycle fields) — asked
directly why the Critic called `get_smell_examples` for the same smell_id
3 times (Pedestal) and again later in the same conversation (Greeter).
Measured before explaining: `map_with_nil_values` has **0** human-confirmed
real examples and **5** synthetic ones (`clj-smells-dataset/smells/*/map_with_nil_values/example_bad_{1..5}.md`).
At the then-current `_POSITIVE_EXAMPLES_CAP` of 2, exhausting 5 examples
takes exactly 3 calls (2+2+1) — matching the Pedestal trace precisely. The
repeat calls weren't wasted duplicates (D14 already prevents that — each
one returned genuinely new content) but the model had no way to know in
advance whether calling again was worth it, since nothing told it how much
more existed.

Separately, that model never resolved the case decisively anyway: none of
the 5 synthetic examples show a `defrecord`/component-lifecycle case (all
five are ad-hoc application map literals — config, profile, error
response, form, user record) — the dataset has no precedent for the actual
question at hand (does a fixed-schema `defrecord` field carry the same
missing-vs-nil ambiguity as an open-schema map literal). The model kept
pulling more evidence hoping to find a matching precedent that
structurally isn't there. Its final reasoning in both traces was correct
and reasonably sophisticated regardless (recognized the fixed-schema vs.
open-schema distinction, correctly returned `confirmed: false`) — this
decision is about the wasted rounds getting there, not a correctness fix,
same framing as D18.

Also from the Pedestal trace: `get_function_source(['defrecord'])` — asking
for the "source" of `defrecord` itself, a Clojure core special form/macro,
not a project-defined function. Handled gracefully already (the tool
correctly reports "not found... likely an external library function") but
the round was still spent asking a category-error question.

**Three changes, in `src/tools/example_lookup.py` and
`src/agents/agentic_critic.py`:**
1. `ExampleStore.count_available(smell_id)` — true total positive/negative
   count (real + synthetic combined), unbounded by the per-call caps.
   `get_smell_examples`'s tool wrapper now appends a line to every non-empty
   result: `"(N of M total examples for this smell sent so far — K more
   available if you need them.)"`, or `"...that's all of them, no need to
   call again."` when exhausted. Gives the model the information to decide
   whether another call is worth it, instead of it being a guess every
   time — same principle as D18's `list_doc_sections`/D14's
   `get_smell_examples` no-resend notices, but proactive instead of only
   reactive (told before the wasted call, not just blocked after).
2. `_POSITIVE_EXAMPLES_CAP`: 2 → 3. Doesn't fix the underlying "no matching
   precedent exists" problem for a case like this one — that's a dataset
   gap, not a budget one — but it does mean exhausting a 5-example pool
   like `map_with_nil_values`'s now takes 2 calls (3+2) instead of 3
   (2+2+1), one fewer round for smells sitting in this size range.
3. `get_function_source`'s docstring now explicitly says it's only for
   names actually defined in the project, naming Clojure/Java core special
   forms and macros (`defrecord`, `defn`, `defprotocol`, `let`, `ns`,
   `assoc`, `str`, ...) as things it won't find and the model already knows.

Verified against the exact scenario from the traces:
`store.count_available('map_with_nil_values')` returns
`{"positive": 5, "negative": ...}` matching the measured file count; with
the cap at 3, two `get_smell_examples` calls in sequence for that smell_id
produce `"(3 of 5 ... — 2 more available)"` then `"(5 of 5 ... — that's all
of them, no need to call again)"`.

**Source:** user-reported, from two real tool-calling transcripts (the
Pedestal `Pedestal`/`Greeter` components) — not an external citation.

---

### D23 — Actual $ cost captured from OpenRouter's `usage.cost`, surfaced per file and per batch

Asked directly whether real cost (not just token counts) could be pulled
from the API response. Researched OpenRouter's docs, then verified against
this repo's own installed libraries before writing anything — no network
calls made; everything below was checked with mocked/simulated responses
(`unittest.mock.patch` on `_generate`/`chat.completions.create`, fake API
keys) so nothing was actually charged while building this.

**What OpenRouter returns:** every response's `usage` object includes
`cost` (OpenRouter's own reported charge for that exact request, in their
credit unit — their docs say "credits," not confirmed here as an exact
1:1 USD peg) and `cost_details.upstream_inference_cost` (what the upstream
provider charged OpenRouter — only populated for BYOK setups). Included
automatically in every response; no request parameter needed (the older
`usage: {include: true}` flag is deprecated and now a no-op).

**Two separate code paths, both verified working, by different mechanisms:**
1. **Detection / rag-mode Critic** (`OpenRouterClient`, raw `openai` SDK).
   `cost` isn't part of OpenAI's own `CompletionUsage` schema, but the
   installed SDK's pydantic model has `model_config = {"extra": "allow"}`
   — verified directly — so `response.usage.cost` survives untouched. New
   `cost_from_openai_usage(usage)` helper in `src/llm/base.py`
   (`getattr(usage, "cost", None)`), wired into both `complete()` and
   `complete_structured()`.
2. **Agentic Critic** (LangChain `ChatOpenAI`). Initially assumed this
   would need switching `.invoke()` to `.generate()` to reach
   `ChatResult.llm_output` — checked directly and that assumption was
   wrong: `BaseChatModel`'s full `.invoke()` pipeline already merges
   `llm_output` (built from a `model_dump()` of the raw response, which
   also preserves the `cost` extra field) into each returned message's
   `response_metadata["token_usage"]["cost"]`. Confirmed by mocking
   `_generate` to return a `ChatResult` built from a fake OpenRouter
   response and calling the actual `.invoke()` this codebase uses — no
   change to the invocation pattern was needed. New
   `AgenticCriticAgent.record_cost(response)` accumulates this across every
   round, mirroring `record_cache_usage()`'s existing pattern exactly;
   wired into `_node_agent`/`_node_force_finalize` alongside the existing
   `record_cache_usage()` call.

**Surfaced at three levels**, all following the D17 aggregation pattern:
- `AgentLLMMetrics.cost` (`src/artifact/schema.py`) — per-agent, per-file,
  in each file's `result.json`.
- Per-file log line, `[file.clj] Cost: $0.NNNNNN`, only when at least one
  agent reported a cost for that file.
- Batch total: `write_summary_json()` sums every file's cost into the
  `summary_*.json`'s top-level `"cost"` key, and `main.py` logs
  `Total Cost: $X` at the end of a run.

`None` is used throughout — not `0` — for "not reported," so a run where
no agent's provider reports cost (e.g. non-OpenRouter providers, or
OpenRouter models/responses that don't include the field) isn't displayed
as free; the per-file and batch-total cost lines are only logged when at
least one real cost value was actually seen.

**Verified, not assumed** — consistent with every other decision in this
document that touches provider response parsing: `cost_from_openai_usage`
tested against a real `CompletionUsage` instance built from OpenRouter's
documented example payload; the LangChain path tested end to end through
the actual `.invoke()` call this codebase uses, with `_generate` mocked to
return a `ChatResult` derived from that same fake response via this
project's own `ChatOpenAI._create_chat_result()`; `write_summary_json()`
run against a temp directory and the output JSON inspected for the new
`"cost"` key. All of this against mocked responses — real API cost
reporting behavior (exact values, whether every OpenRouter model/route
populates the field) is not yet confirmed against a live run's logged
output.

**Sources:**
- OpenRouter — *"Usage Accounting"*,
  openrouter.ai/docs/cookbook/administration/usage-accounting (`usage.cost`
  field, automatic inclusion, credit unit, example response JSON).
- `openai` Python SDK (installed in `.venv`) —
  `openai.types.completion_usage.CompletionUsage.model_config` inspected
  directly to confirm `extra: "allow"`, rather than assuming unknown fields
  survive.
- `langchain-openai` 1.5.0 (installed in `.venv`) — `ChatOpenAI._create_chat_result()`
  and the full `.invoke()`/`.generate()` pipeline exercised directly (not
  just read) to confirm `cost` reaches `response_metadata`, correcting an
  initial wrong assumption that `.generate()` would be required.

---

### D24 — Non-agentic path moved onto LangChain too; `LLMClient` now has one implementation, not five

D8 accepted a real duplication: `src/llm/*_client.py` hand-wrapped each
provider's native SDK for Detection/rag-mode Critic, while the agentic
Critic built LangChain `BaseChatModel`s for the same five providers because
`.bind_tools()` needs one. Asked directly whether that duplication was worth
removing now that the codebase already pays LangChain's dependency and
per-provider-quirk cost for the agentic path — concluded yes: the two
factories (`main.py::_build_llm`'s per-provider branches and
`agentic_critic.py::build_chat_model()`) were solving the identical problem
(build something that can call provider X), and `GeminiClient` was already
proof this works — it had quietly been implemented on top of
`ChatGoogleGenerativeAI` since before this decision, not the raw `google`
SDK, with no issues.

**What changed:**
- `src/llm/openai_client.py`, `anthropic_client.py`, `gemini_client.py`,
  `openrouter_client.py`, `ollama_client.py` — deleted.
- `src/llm/chat_models.py` (new) — `build_chat_model()`, moved verbatim from
  `agentic_critic.py` (import updated there: `from ..llm.chat_models import
  build_chat_model`, so the tests that monkeypatch
  `"src.agents.agentic_critic.build_chat_model"` by string path kept working
  unchanged — patching a re-exported name still patches the attribute on
  that module). Also gained an explicit `max_tokens=8192` on the Anthropic
  branch, carrying D15's reasoning (adaptive-thinking budget can truncate a
  tight-`max_tokens` JSON response) into the one branch that previously only
  had it in the now-deleted `AnthropicClient` — a deliberate, low-risk
  behavior change for the agentic Critic's Anthropic calls, not just the
  non-agentic path.
- `src/llm/langchain_client.py` (new) — `LangChainLLMClient`, one
  `LLMClient` implementation for all five providers, generalizing the
  pattern `GeminiClient` already used: `.invoke()` for `complete()`,
  `.with_structured_output(schema, include_raw=True)` for
  `complete_structured()` (letting LangChain pick the right underlying
  mechanism per provider — tool-calling for Anthropic/Gemini, native JSON
  schema for OpenAI, JSON mode for OpenRouter/Ollama — instead of this
  project hand-picking one per provider), falling back to the base class's
  text-parse path on any failure, same as `OpenRouterClient`/`OpenAIClient`
  did before.
- `src/llm/base.py` — `cache_tokens_from_openai_usage`/
  `cost_from_openai_usage` (dead once the raw-SDK clients were gone) removed;
  replaced by `cache_tokens_from_langchain_usage`/`cost_from_langchain_response`,
  reading `AIMessage.usage_metadata`/`response_metadata` (same fields D13/D23
  already verified against real `.invoke()` calls). `_mark_cache_breakpoint`
  also moved here from `agentic_critic.py`, since `LangChainLLMClient` needs
  it too (D17's system-message breakpoint, not just D13's tail-of-conversation
  one). `AgenticCriticAgent.record_cache_usage`/`record_cost` and
  `Orchestrator._log_cache_usage` now call these shared helpers instead of
  each inlining the same extraction logic (previously duplicated three ways).
- `main.py::_build_llm` — one branch (`LangChainLLMClient(provider, model,
  api_key, use_prompt_cache)`) instead of five, with its own unknown-provider
  check kept (`LangChainLLMClient`'s underlying error, from `build_chat_model`,
  names a different context and shouldn't leak through `_build_llm`'s public
  error message).
- `requirements.txt` — direct `openai`/`anthropic` SDK pins removed (still
  installed transitively via `langchain-openai`/`langchain-anthropic`, which
  is now the only thing in this project that imports them).

**What deliberately didn't change:** `Detector`, `Critic` (rag mode),
`Orchestrator`, `with_retry`, and `main.py`'s stats aggregation — all of
these depend only on the `LLMClient`/`LLMResponse` interface (§ "Provider
abstraction" in `CLAUDE.md`), never on how a client is implemented
internally, so none needed to change. This is why a migration touching every
LLM call in the project stayed contained to `src/llm/*.py` +
`main.py::_build_llm` + one import line in `agentic_critic.py` — the
`LLMResponse` dataclass was already the right seam, from D1.

**Testing:** `tests/test_llm_clients.py` rewritten against
`LangChainLLMClient` (provider-agnostic behavior — usage/content
normalization, cache/cost extraction, the OpenRouter system-message
breakpoint, structured-output fallback — monkeypatching `.invoke()`/
`.with_structured_output()` on the real LangChain model class, same pattern
the pre-existing `GeminiClient` tests already used). New
`tests/test_chat_models.py` covers `build_chat_model()`'s per-provider
dispatch, including the new Anthropic `max_tokens` assertion (the
single redundant `unknown provider` test in `test_agentic_critic.py` was
removed in favor of it). `tests/test_main.py`'s `_build_llm` dispatch tests
updated to assert the single `LangChainLLMClient` call instead of five
per-provider classes. `tests/test_detection.py`, `tests/test_critic.py`, and
`tests/conftest.py` needed **no changes** — already written against
`FakeLLMClient`, fully decoupled from any concrete client. Full suite (211
tests) verified passing offline; no real API call was made anywhere in this
migration.

---

## 4. Standards validation

### 4.1 — Should this adopt Agent Skills (`SKILL.md`)?

**Short answer: not as the literal runtime mechanism, for a structural
reason — but the file *format* is worth aligning with.**

This needed re-checking mid-project because the premise changed under us:
Agent Skills was Anthropic-only when first considered here, but Anthropic
published it as an **open standard in December 2025**, and OpenAI (Codex
CLI, Feb 2026) and Google (Gemini CLI) adopted it shortly after — the three
now co-govern it under the Agentic AI Foundation (Linux Foundation). As of
mid-2026 it's supported by 20-40+ agent products (Claude Code, Codex CLI,
Cursor, Gemini CLI, GitHub Copilot, OpenCode, ...). The premise "Skills only
works with Claude" is no longer accurate, and it was fair to be challenged
on it.

What doesn't change with that correction: Agent Skills is interpreted at
the **agent-harness / reasoning-loop layer** — Claude Code, Gemini CLI,
Cursor, Codex CLI, etc. are the programs that discover `SKILL.md` files,
inject name+description, and load the body on activation. It is not a
feature of the raw model APIs. This pipeline calls Gemini/OpenAI/
Anthropic/OpenRouter/Ollama **directly** through LangGraph — it does not run
inside any Skills-aware harness. Dropping a `SKILL.md` file into this repo
would not be auto-discovered by anything in this codebase; the discovery
and loading logic would still have to be hand-written — which is exactly
what `ExampleStore` + `AgenticCriticAgent`'s tools already are.

**Recommendation (not yet implemented):** the *format* itself is now simple,
standardized, and well-specified (YAML frontmatter: required `name` +
`description`, optional `version`/`compatible_agents`, Markdown body). The
`docs/` convention this project invented ad hoc (`# Heading [#anchor]`, see
`clj-smells-dataset/docs/README.md`) could be upgraded to literal
`SKILL.md`-compliant structure at low cost — same effort, but standards-
compliant, and it would make the dataset directly usable if anyone ever
opens it in Claude Code / Gemini CLI / Cursor by hand. Worth doing as a
follow-up, not required for the pipeline to function.

**Sources:**
- Anthropic — *"Effective Context Engineering for AI Agents"* (progressive
  disclosure, the pattern Skills formalizes).
- agentskills.io / Agentic AI Foundation adoption reporting (industry,
  cross-checked across multiple independent sources: agensi.io, F5 blog,
  agentman.ai) — December 2025 open publication, OpenAI/Google adoption in
  early-to-mid 2026, SKILL.md frontmatter spec (`name`, `description`
  required).

### 4.2 — Should this adopt MCP (Model Context Protocol)?

**No.** MCP standardizes exposing tools/resources across a *process/client
boundary* — useful when the same tool needs to be reachable from multiple,
separate agent products (e.g. also usable from Claude Desktop, not just this
pipeline). `ExampleStore`'s tools are called in-process, by this repo's own
LangGraph graph, in the same Python process as `main.py` — there is no
second client that needs to reach them. Wrapping them as an MCP server would
add a server process, a client connection, and JSON-RPC serialization for
zero functional gain here. Reconsider if these tools ever need to be called
from outside this pipeline.

---

## 5. Empirical validation (measured on this repository)

Same input file (`samples/sample_smelly_subtle.clj`, 8 candidates), same
model (`gemini-flash-latest`), `--retrieval agentic`, before vs. after
applying D5 (index → tool) and D6 (batched tool calls):

| | Before | After |
|---|---|---|
| Tool calls made | 8 (one per smell) | 1 (all smells batched) |
| Critic prompt tokens | 22,193 | — |
| Full pipeline prompt tokens (Detection+Critic) | — | 9,671 |
| Verdicts confirmed | 8/8 | 8/8 (unchanged) |

Accuracy held constant; token cost dropped by more than half even counting
the full pipeline against the critic-only baseline. This is the strongest
evidence in this document, precisely because it's this repository's own
data, not a transferred benchmark.

Separately (§D11): after merging the two graphs into one, the same file was
re-run end to end against the live API (surviving two transient 503s via
retry) and produced the same 8/8 confirmed verdicts — the merge changed
structure, not behavior.

---

## 6. Open follow-ups

- Align `docs/` convention with the literal `SKILL.md` frontmatter spec
  (§4.1) — low cost, gives standards compliance and external-tool
  compatibility for free.
- Measure D13's actual cache-hit rate on a live run — the `[AgenticCritic][cache]`
  log line D13 added reports `prompt_tokens`/`cached_tokens`/
  `cache_write_tokens` per call, but no run's output has been reviewed for
  this yet. This is the natural next step, and would also settle whether
  OpenRouter's minimum-token-threshold requirement is actually met by this
  pipeline's prefix size in practice.
- Tool-schema caching (the 5 tool definitions resent every round, on any
  provider) — flagged as a follow-up in both D12 (Anthropic) and D13
  (OpenRouter); requires bypassing LangChain's `bind_tools()` tool-schema
  conversion to attach a cache marker to the tools array itself.
- Measure D12's actual before/after token cost on this pipeline, the way D5
  and D6 were measured (§5) — no local measurement exists yet.
- Graph-based retrieval for the namespace/dependency-shaped smells
  (`excessive_refers`, `implicit_namespace_dependencies`,
  `monolithic_namespace_split`, ...) — flagged earlier as a structural fit,
  not built; would need real namespace/require graphs from ingested
  projects, which the dataset doesn't have yet.
- Cross-namespace resolution for `get_function_source` currently relies on
  a project-wide text search (§2.3) rather than resolving Clojure's
  namespace→file convention (`app.utils` → `app/utils.clj`) directly —
  works, but a smarter resolver would be more precise on large projects.

---

## 7. References

**Peer-reviewed:**
- Wei et al. — *Chain-of-Thought Prompting Elicits Reasoning in Large
  Language Models* — NeurIPS 2022.
- *Stronger Baselines for Retrieval-Augmented Generation with Long-Context
  Language Models* — EMNLP 2025 (ACL Anthology).
- *What to Retrieve for Effective Retrieval-Augmented Code Generation? An
  Empirical Study and Beyond* — ICSE 2026 Research Track.
- *iSMELL: Assembling LLMs with Expert Toolsets for Code Smell Detection
  and Refactoring* — ASE 2024 (IEEE/ACM), also IEEE Xplore.
- *Pioneering agentic retrieval-augmented generation in software quality: a
  novel framework for code smell detection via dynamic retrieval* — PeerJ
  Computer Science, 2026.
- Amazon Science — agentic keyword search vs. RAG faithfulness measurement
  — AAAI 2026.
- *Graph Retrieval-Augmented Generation: A Survey* — ACM Transactions on
  Information Systems, v.44 n.2 (2025).
- *Graph-Based Approaches and Functionalities in Retrieval-Augmented
  Generation: A Comprehensive Survey* — ACM Computing Surveys (2025).
- *Constructing and Evaluating Declarative RAG Pipelines in PyTerrier* —
  SIGIR 2025 (ACM).

**Industry primary sources (not peer-reviewed, but authoritative):**
- Anthropic — *Building Effective Agents* (Dec 2024).
- Anthropic — *Effective Context Engineering for AI Agents* (Sept 2025).
- Anthropic — Claude Code dropping vector search for agentic grep (May
  2025), cross-reported adoption by Cursor/Windsurf/Cline/Devin/
  Sourcegraph Amp.
- Anthropic — Agent Skills open standard publication (Dec 2025) and
  cross-vendor adoption (OpenAI Codex CLI, Google Gemini CLI, early-to-mid
  2026), per agentskills.io ecosystem reporting.

**Preprints (arXiv, not peer-reviewed — cite with that caveat):**
- cAST — *Enhancing Code Retrieval-Augmented Generation with Structural
  Chunking via Abstract Syntax Tree* (arXiv 2506.15655).
- *Retrieval-Augmented Code Generation: A Survey with Focus on
  Repository-Level Approaches* (arXiv 2510.04905).
- *Practical Code RAG at Scale: Task-Aware Retrieval Design Choices under
  Compute Budgets* (arXiv 2510.20609).
- 2026 multi-turn tool-calling cost analysis (sequential-call token-cost
  finding, §D6).

**This repository:**
- §5, measured directly on this codebase, 2026-08-13/14.
