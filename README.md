# clj-smells-llm-detection

Multi-agent pipeline for detecting Clojure code smells using LLMs.

## How it works

```
.clj file → Detector → AST Extraction → Retrieval → Critic → verdict
```

1. **Detector** — one LLM call, scans the target `.clj` file against a catalog of 34 smells and returns a list of suspects
2. **Extraction** — pulls the exact AST-scoped code (function/namespace) per suspect via Babashka + `rewrite-clj`
3. **Retrieval** — evidence for the Critic, via one of two interchangeable strategies (`--retrieval`):
   - `agentic` (default) — no vector DB. The Critic itself decides, per candidate, whether it needs more evidence and pulls it on demand via tool calls (LangGraph) straight from `clj-smells-dataset/`. This is the only genuinely *agentic* piece in the pipeline — it's the one component that decides for itself whether/when to act.
   - `rag` — `Retriever` pre-fetches labeled examples from a vector DB (ChromaDB + embeddings) for every candidate, before the Critic runs. Pass `--retrieval rag` explicitly to use it.
   
   See [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md) for the full rationale and a [diagram](https://claude.ai/code/artifact/3bc9e05f-a848-4161-9f7c-c46bb0ee6136) of both paths.
4. **Critic** — judges each suspect using the retrieved context and produces a verdict with Chain-of-Thought reasoning

Naming note: `Detector`, `Retriever`, and `Critic` are each a single deterministic
step (an LLM call, or in `Retriever`'s case not even that) — only the agentic
critic (`AgenticCriticAgent`) is an agent in the strict sense. See
`ARCHITECTURE_DECISIONS.md` for why they're named this way.

The result is written as a JSON file with verdicts, latencies, and token usage per step, plus a `.md` trace (full prompts/responses — including the tool-calling transcript in `agentic` mode).

---

## Requirements

- Python 3.11+
- An API key for at least one provider (see below)

---

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd clj-smells-llm-detection

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API key
cp .env.example .env
# Edit .env and fill in the key for the provider you want to use
```

---

## Running

### Quickstart — Gemini

```bash
# Set your key in .env:
# GOOGLE_API_KEY=your-key-here

# Default: --retrieval agentic (LangGraph, no vector DB) — no flag needed
python main.py --input samples/sample_smelly.clj --llm gemini
```

### Retrieval strategy: agentic (default) vs RAG

```bash
# Default — the Critic fetches evidence on demand via tool calls, no vector DB, no --retrieval flag needed
python main.py --input samples/sample_smelly_subtle.clj --llm gemini

# Same thing, explicit
python main.py --input samples/sample_smelly_subtle.clj --llm gemini --retrieval agentic

# Agentic, pointing at a different local copy of the dataset (default: ../clj-smells-dataset)
python main.py --input samples/sample_smelly_subtle.clj --llm gemini --retrieval agentic --dataset-path ../clj-smells-dataset

# Opt into the static RAG path instead (ChromaDB + embeddings, pre-fetched for every candidate)
python main.py --input samples/sample_smelly_subtle.clj --llm gemini --retrieval rag --vectordb chroma
```

### Using Ollama (no API key needed)

```bash
# Make sure Ollama is running and the model is pulled:
# ollama pull llama3.1

python main.py --input samples/sample_smelly.clj --llm ollama --detection-model llama3.1 --critic-model llama3.1
```

### Using OpenRouter (one key, any model)

```bash
# Set OPENROUTER_API_KEY in .env

# Gemini via OpenRouter
python main.py --input samples/sample_smelly.clj \
  --llm openrouter \
  --detection-model google/gemini-2.0-flash-001 \
  --critic-model google/gemini-2.0-flash-001

# Claude via OpenRouter
python main.py --input samples/sample_smelly.clj \
  --llm openrouter \
  --detection-model anthropic/claude-3-5-sonnet \
  --critic-model anthropic/claude-3-5-sonnet

# Mix providers: detect with Gemini, judge with Claude
python main.py --input samples/sample_smelly.clj \
  --llm openrouter \
  --detection-model google/gemini-2.0-flash-001 \
  --critic-model anthropic/claude-3-5-sonnet
```

### Processing a directory

```bash
python main.py --input path/to/project/ --dir --llm gemini
```

---

## All CLI options

| Flag | Default | Description |
| --- | --- | --- |
| `--input` / `-i` | *(required)* | Path to `.clj`/`.cljs`/`.cljc` file, or a directory (use `--dir`) |
| `--dir` | `false` | Treat `--input` as a directory and process all Clojure files recursively |
| `--llm` | *(unset)* | Shortcut: same provider for both Detector and Critic — `gemini`, `openai`, `anthropic`, `openrouter`, `ollama` |
| `--detection-llm` | `gemini` | Provider for the Detector, if not using `--llm` |
| `--critic-llm` | `gemini` | Provider for the Critic, if not using `--llm` |
| `--model` | *(unset)* | Shortcut: same model for both Detector and Critic |
| `--detection-model` | `gemini-flash-latest` | Model for the Detector, if not using `--model` |
| `--critic-model` | `gemini-flash-latest` | Model for the Critic, if not using `--model` |
| `--retrieval` | `agentic` | `agentic`: Critic fetches evidence on demand via tools, no vector DB. `rag`: `Retriever` pre-fetches from `--vectordb` before the Critic runs |
| `--vectordb` | `mock` | Vector DB provider — only used when `--retrieval=rag`: `mock` or `chroma` |
| `--dataset-path` | `../clj-smells-dataset` | Path to the dataset root — only used when `--retrieval=agentic` |
| `--output-dir` | `./results` | Output directory |
| `--workers` | `1` | Parallel workers for processing multiple files |
| `--yes` / `-y` | `false` | Skip confirmation prompts |
| `--skip-existing` | `false` | Skip files that already have a `_result.json` in the output directory |
| `--retries` | `3` | Max retries on malformed output or timeout |
| `--catalog` | `smells_catalog.json` | Path to the full smells catalog JSON |
| `--catalog-short` | `smells_catalog_short.json` | Path to the shortened catalog JSON (used in the Detector's prompt) |

---

## Output

Each processed file produces a `_result.json` and a `_trace.md` (full prompts,
responses, and — in `agentic` mode — the tool-calling transcript). Shape of
the JSON, default `--retrieval agentic` run:

```json
{
  "file": "samples/sample_smelly_subtle.clj",
  "run_id": "uuid",
  "timestamp": "2026-08-13T21:05:05Z",
  "agents": {
    "detection": {
      "model": "gemini-flash-latest",
      "prompt_tokens": 1840,
      "completion_tokens": 210,
      "total_tokens": 2050,
      "latency_ms": 1100,
      "retries_used": 0
    },
    "retrieval": {
      "vector_db": "agentic-tool",
      "calls": 1,
      "latency_ms": 6
    },
    "critic": {
      "model": "gemini-flash-latest",
      "prompt_tokens": 7831,
      "completion_tokens": 3906,
      "total_tokens": 11737,
      "latency_ms": 6300,
      "retries_used": 0
    }
  },
  "total_latency_ms": 12439,
  "retries": 0,
  "candidate_smells": [...],
  "verdicts": [
    {
      "smell_id": "unmanaged_resource_io",
      "confirmed": true,
      "confidence": "high",
      "reasoning": "The reader is opened without with-open...",
      "evidence_used": ["catalog_synthetic:example_bad_1.md"]
    }
  ]
}
```

With `--retrieval rag`, `agents.retrieval.vector_db` is `mock` or `chroma`
(whatever `--vectordb` was set to) instead of `agentic-tool`, and `calls`
counts one query per candidate rather than tool calls.

---

## Project structure

```
clj-smells-llm-detection/
├── main.py                     # CLI entrypoint
├── config.py                   # Settings (reads from .env)
├── smells_catalog.json         # 34 Clojure code smells (Detector prompt)
├── ARCHITECTURE_DECISIONS.md   # Why each design choice was made, with sources
├── samples/
│   ├── sample_smelly.clj           # Obvious/textbook smells
│   └── sample_smelly_subtle.clj    # Subtler smells, exercises the agentic tools
└── src/
    ├── agents/
    │   ├── detection.py        # Detector — one LLM call
    │   ├── retrieval.py        # Retriever — no LLM at all, --retrieval rag only
    │   ├── critic.py           # Critic — one LLM call, --retrieval rag only
    │   ├── agentic_critic.py   # AgenticCriticAgent — the actual agent, --retrieval agentic
    │   └── formatting.py       # Shared evidence formatting for both critics
    ├── tools/
    │   └── example_lookup.py   # ExampleStore — on-demand file reads backing the agentic tools
    ├── orchestrator/
    │   ├── orchestrator.py     # Pipeline coordinator + latency tracking, both retrieval modes
    │   └── retry.py            # Retry on malformed JSON or timeout
    ├── llm/
    │   ├── base.py             # LLMClient interface + LLMResponse dataclass + shared normalization helpers
    │   ├── chat_models.py      # build_chat_model() — LangChain BaseChatModel factory, all 5 providers
    │   └── langchain_client.py # LangChainLLMClient — the one LLMClient impl, built on chat_models.py
    ├── vectordb/
    │   ├── base.py             # VectorDBClient interface + ContextPackage
    │   ├── mock_client.py      # Hardcoded/dataset-backed examples (PoC)
    │   └── chroma_client.py    # ChromaDB + Gemini embeddings, --retrieval rag
    ├── catalog/
    │   └── loader.py           # Loads smells_catalog.json
    └── artifact/
        ├── schema.py           # Pydantic models for the output JSON
        └── validator.py        # Parses + validates LLM output, triggers retry
```

---

## Adding a new LLM provider

One factory covers both retrieval modes (D24): add a branch to
`build_chat_model()` in `src/llm/chat_models.py` returning the right
LangChain `BaseChatModel` for the new provider (`ChatOpenAI`, `ChatAnthropic`,
`ChatGoogleGenerativeAI`, or an OpenAI-compatible endpoint via `ChatOpenAI`
with a different `base_url`, as OpenRouter/Ollama already do), and add the
provider name to `SUPPORTED_LLM_PROVIDERS` in `main.py`. `--retrieval agentic`
(`.bind_tools()`) and `--retrieval rag`/detection (`LangChainLLMClient` in
`src/llm/langchain_client.py`) both pick it up automatically — neither needs
its own per-provider code.

## Adding a real vector DB

1. Create `src/vectordb/<name>_client.py` implementing `VectorDBClient`
2. Register in the `_build_vectordb` factory in `main.py`
3. Index documents with the schema: `smell_id`, `label` (`positive`/`negative`/`refactoring`/`survey_comment`/`doc`), `code`, `source`, `description`
