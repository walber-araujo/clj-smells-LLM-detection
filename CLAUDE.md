# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Keeping this file current

This file should be updated whenever it goes stale — it isn't written once
and forgotten. In particular, notes describing transitional project state
(no tests yet, no repo yet, etc.) should be fixed or removed as soon as
they stop being true instead of lingering as stale claims.

## What this is

A multi-agent pipeline that detects Clojure code smells using LLMs:
`.clj file → Detector → AST Extraction → Retrieval → Critic → verdict`. See
`README.md` for the full CLI reference, output JSON shape, and how to add a
new LLM provider or vector DB — don't duplicate that here.

## Commands

```bash
pip install -r requirements.txt
cp .env.example .env               # fill in an API key for at least one provider

# Single file, default retrieval mode (agentic, no vector DB)
python main.py --input samples/sample_smelly.clj --llm gemini

# Explicit RAG mode (ChromaDB + embeddings, pre-fetched per candidate)
python main.py --input samples/sample_smelly.clj --llm gemini --retrieval rag --vectordb chroma

# Whole directory
python main.py --input path/to/project/ --dir --llm gemini

# Test suite (pytest, offline — no network/LLM calls, no API keys needed)
python -m pytest
python -m pytest tests/test_orchestrator.py -k agentic_mode  # single file/test
```

There is no configured lint. `test_parse.py` / `test_parse2.py` at the repo
root are unrelated ad-hoc manual scripts (pre-date `tests/`), not part of
the suite. Everything under `tests/` mocks or fakes out the network/SDK
boundary (LLM clients' `.complete()`, `subprocess` for Babashka, LangChain
chat models bound to `AgenticCriticAgent`) — none of it calls a real model
or hits the network; see `pytest.ini` (`pythonpath = .`) for how imports
resolve without an installed package.

Extraction (`src/extractor/extract.clj`) requires **Babashka (`bb`)** on
`PATH` — both `_node_extract` (orchestrator.py) and the agentic critic's
`get_function_source` tool shell out to it via `subprocess`, and silently
fall back to full-file context if `bb` isn't found.

## Architecture

**One LangGraph graph, two modes.** `Orchestrator` (`src/orchestrator/orchestrator.py`)
builds a single `StateGraph(PipelineState)` covering the whole pipeline —
`pre_filter → detect → extract → judge`. `--retrieval agentic` (default) and
`--retrieval rag` are two different tails wired onto the *same* graph object,
selected by `mode` at construction time, not two separate pipelines:
- `rag`: `extract → judge_rag → END`. `Retriever` pre-fetches vector-DB
  evidence for every candidate before `Critic` (`src/agents/critic.py`) runs
  once.
- `agentic`: `extract → prepare_agentic → agent ⇄ tools → finalize_agentic`.
  No vector DB. `AgenticCriticAgent` (`src/agents/agentic_critic.py`) is
  *not* itself a graph — it only supplies the bound LangChain chat model,
  tools, and prompt/parsing logic; `Orchestrator` owns the actual cycle
  (`agent` node ⇄ `ToolNode`). An earlier version ran this cycle as its own
  nested graph; see `ARCHITECTURE_DECISIONS.md` decision log for why that
  was collapsed into one graph.

**`tool_rounds` budget vs. `recursion_limit`.** The agentic loop enforces its
own round cap (`AgenticCriticAgent.max_tool_rounds`, default 6) via
`_route_agent`: once hit, it routes to `force_finalize` instead of `tools`,
which re-invokes the model with tools *unbound* so it's structurally unable
to request another round. LangGraph's `recursion_limit` (set in
`Orchestrator.run()`) is a generous safety net on top of that, not the real
limit — it should never actually be reached in normal operation.

**Per-smell extraction scope.** `SMELL_SCOPE` in `orchestrator.py` maps a few
smell IDs to `ns_form` or `file` scope (namespace-level or whole-file smells
like `namespace_load_side_effects`); everything else defaults to
function-level extraction via `extract.clj`.

**Agentic tools are stateful per file-run.** `AgenticCriticAgent.reset_run()`
must be called once per file (done by `_node_prepare_agentic`) — it resets
tool-call counters and the `_examples_sent` dedup state so
`get_smell_examples` tracks, per `smell_id`, which examples were already
sent this run and returns the next unseen batch on repeat calls rather than
resending or repeating. The four tools (`get_smell_examples`,
`list_doc_sections`, `get_doc_section`, `get_function_source`) are all
backed by `ExampleStore` (`src/tools/example_lookup.py`), which reads
straight from `clj-smells-dataset/` — no embeddings involved in agentic mode.

**One LangChain factory backs every LLM call, agentic or not (D24).**
`src/llm/chat_models.py::build_chat_model()` builds a LangChain
`BaseChatModel` per provider; `src/llm/langchain_client.py::LangChainLLMClient`
is this project's single `LLMClient` implementation (used by `Detector` and
the RAG-mode `Critic`), built on top of that same factory, while
`agentic_critic.py` binds tools onto it directly (`.bind_tools()`) for the
agentic path. Adding a new provider means touching one factory
(`build_chat_model()`) plus `SUPPORTED_LLM_PROVIDERS` in `main.py` — see
README's "Adding a new LLM provider" section. `Detector`/`Critic`/
`Orchestrator` only depend on the `LLMClient`/`LLMResponse` interface, never
on how a client is implemented, which is why this unification (previously
five bespoke per-provider clients) didn't touch any of them.

**Prompt caching is provider-specific and load-bearing for cost**, not just
an optimization: in agentic mode the entire conversation is resent every
tool-call round, so `AgenticCriticAgent` marks Anthropic (`cache_control`)
and OpenRouter (`prompt_cache_breakpoint` + a stable `session_id` from
`reset_run()`) requests explicitly. `with_cache_breakpoint()` is OpenRouter-only
and moves the breakpoint to the tail of the conversation before each `agent`
node call. `_node_force_finalize` deliberately does *not* mark a breakpoint,
since that call uses the tools-unbound model (a different request shape that
can't read the tool-bound cache, and is always the run's last call anyway).

**Retry policy is per-node, not global.** `with_retry` (`src/orchestrator/retry.py`)
wraps `_node_detect` and `_node_judge_rag`; the agentic path retries inline
inside `_node_finalize_agentic` (malformed JSON triggers a `HumanMessage`
asking the model to retry, up to `max_retries`, before raising
`MaxRetriesExceeded`).

For the reasoning behind any of the above (including a full decision log
with sources), see `ARCHITECTURE_DECISIONS.md` — it's kept current and is
the authoritative "why," not this file.

## Session summaries (`./`)

Every relevant work session in this repo uses the `session-summaries` skill
(`~/.claude/skills/session-summaries/`) — invoke it, don't reinvent the
format. In practice that means:

- **At the start**, skim the `SESSION_SUMMARY_*.md` titles in the project
  root before investigating something from scratch — it's common for the
  topic to already be resolved in an earlier session.
- **During the work**, keep the current session's `.md` updated as work
  progresses, not just at the very end — rewrite/condense, don't just append.
- **At the end**, delete summaries whose problem is already resolved and
  that carry no investigation context worth preserving.

Existing summaries are written in Portuguese — keep that going. File
prefix: `SESSION_SUMMARY` (e.g. `SESSION_SUMMARY_2026-08-14.md`), directory
is the project root. Format, full lifecycle, and content rules: see the
skill.

## Testing requirement

Every behavioral change (bug fix or feature) must come with a test that
covers it — one that would fail without the fix, or that exercises the new
behavior. This holds even when the change was verified manually (running
`python main.py` against a sample, inspecting output JSON, etc.): manual
verification doesn't substitute for an automated test, because it doesn't
survive the next change. See "Commands" above for how the suite (`pytest`,
offline, no network/LLM calls) is organized and run.

Exceptions: the user explicitly asks for no test, or the change is purely
non-functional (e.g. docs/comments) with nothing to exercise — in that case
say so explicitly rather than silently skipping.
