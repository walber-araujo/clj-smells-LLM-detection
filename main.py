#!/usr/bin/env python3
"""
clj-smells — Multi-agent Clojure code smell detection.

Providers supported:
  openai       → OpenAI (GPT-4o, GPT-4-turbo...)
  anthropic    → Anthropic (Claude 3.5 Sonnet...)
  gemini       → Google Gemini (gemini-2.0-flash, gemini-1.5-pro...)
  openrouter   → OpenRouter gateway (any model, e.g. google/gemini-2.0-flash-001)
  ollama       → Local Ollama (llama3.1, gemma3...)

Usage examples:
  # Single file (default)
  python main.py --input path/to/file.clj --llm openai --model gpt-4o

  # Directory
  python main.py --input path/to/project/ --dir --llm anthropic

  # With custom output path
  python main.py --input file.clj --output results/output.json

  # Override retries
  python main.py --input file.clj --retries 5
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from config import config
from src.catalog.loader import load_catalog
from src.agents.detection import Detector
from src.agents.retrieval import Retriever
from src.agents.critic import Critic
from src.agents.agentic_critic import AgenticCriticAgent
from src.tools.example_lookup import ExampleStore
from src.orchestrator.orchestrator import Orchestrator
from src.orchestrator.retry import MaxRetriesExceeded
from src.utils.io import write_result_and_trace, write_summary_json, get_output_paths

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── LLM factory ──────────────────────────────────────────────────────────────

SUPPORTED_LLM_PROVIDERS = ["openai", "anthropic", "gemini", "openrouter", "ollama"]


def _build_llm(provider: str, model: str, use_prompt_cache: bool = False):
    """`use_prompt_cache`: only meaningful for `provider == "openrouter"`
    (D17) — mark its system message as a cache breakpoint. Only worth
    `True` when this client will be reused across multiple `complete()`
    calls with the same `system` text, i.e. batch/directory mode (`--dir`),
    where a later file's first call can read back what an earlier file's
    call wrote. On a single file there's no later call to benefit, so the
    caller should pass `False` (the default) there. Harmless no-op for
    every other provider — this project only has a sourced, verified
    answer for the OpenRouter transport (see D13/D17 in
    ARCHITECTURE_DECISIONS.md)."""
    if provider not in SUPPORTED_LLM_PROVIDERS:
        raise ValueError(f"Unknown LLM provider: '{provider}'. Supported: {SUPPORTED_LLM_PROVIDERS}")
    from src.llm.langchain_client import LangChainLLMClient
    return LangChainLLMClient(
        provider=provider, model=model, api_key=_api_key_for(provider),
        use_prompt_cache=use_prompt_cache,
    )


def _api_key_for(provider: str) -> str:
    return {
        "openai": config.openai_api_key,
        "anthropic": config.anthropic_api_key,
        "gemini": config.google_api_key,
        "openrouter": config.openrouter_api_key,
        "ollama": "",
    }.get(provider, "")


# ── VectorDB factory ──────────────────────────────────────────────────────────

def _build_vectordb(provider: str):
    if provider == "mock":
        from src.vectordb.mock_client import MockVectorDBClient
        return MockVectorDBClient()
    if provider == "chroma":
        from src.vectordb.chroma_client import ChromaVectorDBClient
        return ChromaVectorDBClient(
            persist_path=config.chromadb_persist_path,
            google_api_key=config.google_api_key,
        )
    raise ValueError(f"Unknown VectorDB provider: '{provider}'. Supported: mock, chroma")



# ── File collection ───────────────────────────────────────────────────────────

def _collect_files(input_path: Path, is_dir: bool) -> list[Path]:
    if is_dir:
        files = []
        for ext in ["*.clj", "*.cljs", "*.cljc"]:
            files.extend(input_path.rglob(ext))
        files = sorted(files)
        if not files:
            logger.error("No .clj, .cljs, or .cljc files found in directory: %s", input_path)
            sys.exit(1)
        return files
    if input_path.suffix not in [".clj", ".cljs", ".cljc"]:
        logger.warning("Input file does not have .clj, .cljs, or .cljc extension: %s", input_path)
    return [input_path]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Multi-agent Clojure code smell detector."
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to a Clojure file (.clj, .cljs, .cljc) or directory (use --dir for directory mode).",
    )
    parser.add_argument(
        "--dir", action="store_true",
        help="Treat --input as a directory and process all Clojure files recursively.",
    )
    parser.add_argument(
        "--llm", default=None,
        choices=SUPPORTED_LLM_PROVIDERS,
        help=f"Shortcut: Use the same LLM provider for both agents (default: {config.llm_provider}).",
    )
    parser.add_argument(
        "--detection-llm", default=config.llm_provider,
        choices=SUPPORTED_LLM_PROVIDERS,
        help=f"LLM provider for the Detection Agent (default: {config.llm_provider}).",
    )
    parser.add_argument(
        "--critic-llm", default=config.llm_provider,
        choices=SUPPORTED_LLM_PROVIDERS,
        help=f"LLM provider for the Critic Agent (default: {config.llm_provider}).",
    )
    parser.add_argument(
        "--model", default=None,
        help="Use the same model for both Detection and Critic agents.",
    )
    parser.add_argument(
        "--detection-model", default=config.detection_model,
        help=f"Model for the Detection Agent (default: {config.detection_model}).",
    )
    parser.add_argument(
        "--critic-model", default=config.critic_model,
        help=f"Model for the Critic Agent (default: {config.critic_model}).",
    )
    parser.add_argument(
        "--vectordb", default=config.vectordb_provider,
        choices=["mock", "chroma"],
        help=f"Vector DB provider — only used when --retrieval=rag (default: {config.vectordb_provider}).",
    )
    parser.add_argument(
        "--retrieval", default="agentic",
        choices=["rag", "agentic"],
        help=(
            "Retrieval strategy for the Critic (default: agentic). "
            "'agentic': the critic fetches examples itself on demand via a tool "
            "(LangGraph), no vector DB or embeddings. "
            "'rag': Retriever pre-fetches examples from --vectordb before the critic runs "
            "(static, embedding-based) — pass this explicitly to use it. See README for details."
        ),
    )
    parser.add_argument(
        "--dataset-path", default="../clj-smells-dataset",
        help="Path to clj-smells-dataset root — only used when --retrieval=agentic (default: ../clj-smells-dataset).",
    )
    parser.add_argument(
        "--output-dir", default="./results",
        help="Output directory path (default: ./results).",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Number of parallel workers for processing files (default: 1).",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompts.",
    )
    parser.add_argument(
        "--retries", type=int, default=config.max_retries,
        help=f"Max retries on malformed output or timeout (default: {config.max_retries}).",
    )
    parser.add_argument(
        "--catalog", default=config.catalog_path,
        help=f"Path to full smells catalog JSON (default: {config.catalog_path}).",
    )
    parser.add_argument(
        "--catalog-short", default=config.catalog_short_path,
        help=f"Path to shortened smells catalog JSON (default: {config.catalog_short_path}).",
    )

    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Skip processing files if their _result.json already exists in the output directory.",
    )

    args = parser.parse_args()

    # --llm is a shortcut that overrides both detection-llm and critic-llm
    if args.llm:
        args.detection_llm = args.llm
        args.critic_llm = args.llm

    # --model is a shortcut that overrides both detection-model and critic-model
    if args.model:
        args.detection_model = args.model
        args.critic_model = args.model

    # ── Setup ────────────────────────────────────────────────────────────────
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        sys.exit(1)

    files = _collect_files(input_path, args.dir)
    
    if not files:
        logger.error("No Clojure files found to process.")
        sys.exit(0)

    output_dir = Path(args.output_dir)
    project_name = input_path.name if args.dir else input_path.parent.name
    project_out_dir = output_dir / project_name

    # Cross-file search scope for get_function_source() in agentic mode:
    # the whole target directory in --dir mode, or just the single file's
    # own directory otherwise.
    search_root = str(input_path if args.dir else input_path.parent)

    existing_files = 0
    for f in files:
        out_json_path, _, _ = get_output_paths(f, input_path, args.dir, project_out_dir)
        if out_json_path.exists():
            existing_files += 1

    logger.info("Found %d Clojure file(s) to process.", len(files))
    
    if existing_files > 0 and not args.yes:
        logger.info("Found %d file(s) that already have results in the output directory.", existing_files)
        ans = input("Do you want to re-evaluate them? (y/n) [n]: ")
        if ans.lower() in ["y", "yes"]:
            args.skip_existing = False
        else:
            args.skip_existing = True

    if not args.yes:
        ans = input("Proceed? (y/n) [y]: ")
        if ans.lower() not in ["", "y", "yes"]:
            logger.info("Aborted by user.")
            sys.exit(0)

    catalog = load_catalog(args.catalog)
    catalog_short = load_catalog(args.catalog_short)

    detection_llm = _build_llm(args.detection_llm, args.detection_model, use_prompt_cache=args.dir)
    detector = Detector(llm=detection_llm, catalog=catalog_short)

    if args.retrieval == "rag":
        critic_llm = _build_llm(args.critic_llm, args.critic_model, use_prompt_cache=args.dir)
        vectordb   = _build_vectordb(args.vectordb)
        retriever  = Retriever(vectordb=vectordb, catalog=catalog)
        critic     = Critic(llm=critic_llm)
    else:
        example_store = ExampleStore(dataset_path=args.dataset_path)
        retriever     = None
        critic        = AgenticCriticAgent(
            provider=args.critic_llm,
            model=args.critic_model,
            example_store=example_store,
            api_key=_api_key_for(args.critic_llm),
        )

    orchestrator = Orchestrator(
        detector=detector,
        retriever=retriever,
        critic=critic,
        vectordb_name=args.vectordb,
        max_retries=args.retries,
        timeout_s=config.timeout_s,
        mode=args.retrieval,
        catalog=catalog,
    )

    # ── Processing Stats ──────────────────────────────────────────────────────
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock
    import time

    stats_lock = Lock()
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cache_read_tokens = 0
    total_cache_write_tokens = 0
    total_cost = 0.0
    have_any_cost = False
    total_time_ms = 0
    total_candidates = 0
    total_confirmed = 0
    success_count = 0
    fail_count = 0
    all_smells = []  # List to store smell dicts for summary.json
    processed_files = []  # List of all files processed in this batch

    def process_file(clj_file: Path):
        nonlocal total_prompt_tokens, total_completion_tokens, total_time_ms
        nonlocal total_cache_read_tokens, total_cache_write_tokens
        nonlocal total_cost, have_any_cost
        nonlocal total_candidates, total_confirmed, success_count, fail_count, all_smells

        out_json_path, out_md_path, rel_path = get_output_paths(
            clj_file=clj_file,
            input_path=input_path,
            is_dir=args.dir,
            project_out_dir=project_out_dir
        )

        if args.skip_existing and out_json_path.exists():
            logger.info("Skipping (already processed): %s", rel_path)
            try:
                data = json.loads(out_json_path.read_text(encoding="utf-8"))
                with stats_lock:
                    processed_files.append(str(rel_path))
                    success_count += 1
                    for v in data.get("verdicts", []):
                        if v.get("confirmed"):
                            all_smells.append({
                                "smell_id": v.get("smell_id"),
                                "file": str(rel_path),
                                "element_name": v.get("element_name")
                            })
            except Exception as e:
                logger.warning("Failed to read existing result file %s: %s", out_json_path, e)
            return

        logger.info("Processing: %s", clj_file)
        code = clj_file.read_text(encoding="utf-8")

        try:
            artifact, trace = orchestrator.run(code=code, file_path=str(clj_file), search_root=search_root)
        except Exception as exc:
            logger.error("Pipeline failed for %s: [%s] %s", clj_file, type(exc).__name__, exc)
            with stats_lock:
                fail_count += 1
            return

        # Determine output path and write result/trace
        out_json_path, rel_path = write_result_and_trace(
            clj_file=clj_file,
            input_path=input_path,
            is_dir=args.dir,
            project_out_dir=project_out_dir,
            artifact=artifact,
            trace=trace
        )

        confirmed = sum(1 for v in artifact.verdicts if v.confirmed)
        logger.info(
            "Done [%s] — %d candidate(s), %d confirmed smell(s). "
            "Total: %.0f ms | Retries: %d | Output: %s",
            clj_file.name,
            len(artifact.candidate_smells),
            confirmed,
            artifact.total_latency_ms,
            artifact.retries,
            out_json_path,
        )
        if artifact.smell_summary:
            logger.info("[%s] Summary of confirmed smells: %s", clj_file.name, artifact.smell_summary)

        # Accumulate metrics — now typed via AgentsMetrics
        det_prompt = artifact.agents.detection.prompt_tokens
        det_comp = artifact.agents.detection.completion_tokens
        crit_prompt = artifact.agents.critic.prompt_tokens
        crit_comp = artifact.agents.critic.completion_tokens
        cache_read = artifact.agents.detection.cache_read_tokens + artifact.agents.critic.cache_read_tokens
        cache_write = artifact.agents.detection.cache_write_tokens + artifact.agents.critic.cache_write_tokens
        # D23: None means "not reported for this agent/provider", not 0 —
        # only add to the file's total (and count it toward the batch total
        # at all) when at least one agent actually reported a cost.
        cost_parts = [c for c in (artifact.agents.detection.cost, artifact.agents.critic.cost) if c is not None]
        file_cost = sum(cost_parts) if cost_parts else None
        if file_cost is not None:
            logger.info("[%s] Cost: $%.6f", clj_file.name, file_cost)

        with stats_lock:
            processed_files.append(str(rel_path))
            success_count += 1
            total_prompt_tokens += (det_prompt + crit_prompt)
            total_completion_tokens += (det_comp + crit_comp)
            if file_cost is not None:
                total_cost += file_cost
                have_any_cost = True
            total_cache_read_tokens += cache_read
            total_cache_write_tokens += cache_write
            total_time_ms += artifact.total_latency_ms
            total_candidates += len(artifact.candidate_smells)
            total_confirmed += confirmed
            
            # Store confirmed smells for summary
            for v in artifact.verdicts:
                if v.confirmed:
                    all_smells.append({
                        "smell_id": v.smell_id,
                        "file": str(rel_path),
                        "element_name": v.element_name
                    })


    # ── Process files concurrently ────────────────────────────────────────────
    start_time = time.time()

    interrupted = False
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(process_file, f) for f in files]
            for future in as_completed(futures):
                pass
    except KeyboardInterrupt:
        interrupted = True
        logger.warning("Interrupted by user (Ctrl+C). Writing partial summary...")

    total_elapsed_ms = (time.time() - start_time) * 1000
    total_tokens = total_prompt_tokens + total_completion_tokens

    # ── Final Report & Summary JSON ──────────────────────────────────────────
    summary_path = write_summary_json(
        project_name=project_name,
        project_out_dir=project_out_dir,
        total_time_ms=total_time_ms,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        processed_files=processed_files,
        all_smells=all_smells,
        total_cache_read_tokens=total_cache_read_tokens,
        total_cache_write_tokens=total_cache_write_tokens,
        total_cost=total_cost if have_any_cost else None,
    )

    logger.info("=========================================")
    logger.info("EXECUTION %s", "INTERRUPTED" if interrupted else "COMPLETE")
    logger.info("Files Processed: %d / %d (%d success, %d failed)", success_count + fail_count, len(files), success_count, fail_count)
    logger.info("Total Real Time: %.0f ms", total_elapsed_ms)
    logger.info("Total Pipeline Time: %.0f ms", total_time_ms)
    logger.info("Total Tokens Used: %d (Prompt: %d, Completion: %d)", total_tokens, total_prompt_tokens, total_completion_tokens)
    if total_cache_read_tokens or total_cache_write_tokens:
        logger.info(
            "Total Cache: %d read, %d written (%.0f%% of prompt tokens served from cache)",
            total_cache_read_tokens, total_cache_write_tokens,
            (100.0 * total_cache_read_tokens / total_prompt_tokens) if total_prompt_tokens else 0.0,
        )
    if have_any_cost:
        logger.info("Total Cost: $%.6f", total_cost)
    logger.info("Total Candidates Found: %d", total_candidates)
    logger.info("Total Smells Confirmed: %d", total_confirmed)
    logger.info("Output Directory: %s", project_out_dir.resolve())
    logger.info("Summary JSON: %s", summary_path.resolve())
    logger.info("=========================================")

if __name__ == "__main__":
    main()
