#!/usr/bin/env python3
"""
ingest_chromadb.py — Ingest validated examples from the clj-smells-dataset into ChromaDB.

What gets ingested
──────────────────

1. Human-curated confirmed real chunks  (smell_verdict == "confirmed")
   Source: clj-smells-dataset/exports/rag_chunks_draft.jsonl
   Label : "positive"
   Source tag: "real_curated"
   These are the highest-confidence examples: real Clojure code from OSS projects,
   confirmed by a human curator as a genuine smell.

2. Catalog synthetic examples — smelly code  (*example_bad_*.md)
   Source: clj-smells-dataset/smells/**/<smell_id>/example_bad_*.md
   Label : "positive"
   Source tag: "catalog_synthetic"
   Hand-crafted smelly examples for every smell in the catalog (130 files, 34 smells).

3. Catalog synthetic examples — clean code  (*example_good_*.md)
   Source: clj-smells-dataset/smells/**/<smell_id>/example_good_*.md
   Label : "negative"
   Source tag: "catalog_synthetic"
   Hand-crafted clean counterparts (42 files). These help the critic
   distinguish smells from idiomatic Clojure.

What is deliberately excluded
──────────────────────────────
• Pending / unvalidated real chunks — ground-truth is unknown, risk of noise.
• Rejected chunks (FP) — not enough examples yet to use as negative class
  from real code; catalog negatives are cleaner for now.

Usage
─────
    python ingest_chromadb.py [--dataset-path PATH] [--persist-path PATH] [--dry-run]

Idempotent: running the script twice will not create duplicate documents
(upsert by document id).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

# ── Setup ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_md_code(text: str) -> str:
    """Extract the first Clojure code block from a .md file."""
    match = re.search(r"```[Cc]lojure\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: any fenced block
    match = re.search(r"```\n(.*?)\n```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def _extract_md_metadata(text: str) -> dict:
    """Extract smell name, location, short explanation from a .md file."""
    exp_match  = re.search(r"\*\s*\*\*Short explanation:\*\*\s*(.*)", text)
    loc_match  = re.search(r"\*\s*\*\*Expected smell location:\*\*\s*(.*)", text)
    name_match = re.search(r"\*\s*\*\*Smell name:\*\*\s*(.*)", text)
    return {
        "explanation" : exp_match.group(1).strip()  if exp_match  else "",
        "location"    : loc_match.group(1).strip()   if loc_match  else "",
        "smell_name"  : name_match.group(1).strip()  if name_match else "",
    }


# ── Collectors ────────────────────────────────────────────────────────────────

def collect_real_curated(jsonl_path: Path) -> list[dict]:
    """
    Load confirmed TP chunks from the JSONL export.
    Returns a list of ingestion-ready dicts.
    """
    if not jsonl_path.exists():
        logger.error("JSONL file not found: %s", jsonl_path)
        return []

    records = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        chunk = json.loads(line)

        if chunk.get("smell_verdict") != "confirmed":
            continue

        code = chunk.get("code_content", "").strip()
        if not code:
            code = chunk.get("full_file_code", "").strip()
        if not code:
            logger.warning("Skipping chunk with empty code: %s", chunk.get("id"))
            continue

        records.append({
            "id"               : chunk["id"],
            "document"         : code,
            "smell_id"         : chunk["smell_id"],
            "label"            : "positive",
            "source"           : "real_curated",
            "origin_type"      : chunk.get("origin_type", "real"),
            "project"          : chunk.get("project", ""),
            "file_name"        : chunk.get("file_name", ""),
            "target_element"   : chunk.get("target_element", ""),
            "reasoning"        : chunk.get("final_reasoning") or chunk.get("llm_suggested_reasoning") or "",
            "reasoning_verdict": chunk.get("reasoning_verdict", "pending"),
        })

    logger.info("Collected %d real curated chunks (confirmed TP).", len(records))
    return records


def collect_catalog_synthetic(smells_dir: Path) -> list[dict]:
    """
    Walk smells/**/<smell_id>/example_{bad,good}_*.md and ingest every snippet.
    Returns a list of ingestion-ready dicts.
    """
    if not smells_dir.exists():
        logger.error("Smells directory not found: %s", smells_dir)
        return []

    records = []
    for md_path in sorted(smells_dir.rglob("*.md")):
        # Expect: smells/<category>/<smell_id>/example_bad_1.md
        smell_id = md_path.parent.name
        category = md_path.parent.parent.name
        name_lower = md_path.stem.lower()

        if "bad" in name_lower:
            label = "positive"
        elif "good" in name_lower:
            label = "negative"
        else:
            logger.debug("Skipping unrecognised md: %s", md_path)
            continue

        text = md_path.read_text(encoding="utf-8")
        code = _extract_md_code(text)
        if not code or len(code) < 10:
            logger.warning("Skipping near-empty code block in: %s", md_path)
            continue

        meta = _extract_md_metadata(text)

        doc_id = (
            f"synthetic__{category}__{smell_id}__{md_path.stem}"
        )
        records.append({
            "id"               : doc_id,
            "document"         : code,
            "smell_id"         : smell_id,
            "label"            : label,
            "source"           : "catalog_synthetic",
            "origin_type"      : "synthetic",
            "project"          : "samples",
            "file_name"        : md_path.name,
            "target_element"   : meta["location"],
            "reasoning"        : meta["explanation"],
            "reasoning_verdict": "accurate",       # hand-crafted by dataset authors
        })

    pos = sum(1 for r in records if r["label"] == "positive")
    neg = sum(1 for r in records if r["label"] == "negative")
    logger.info(
        "Collected %d catalog synthetic entries (%d positive, %d negative).",
        len(records), pos, neg,
    )
    return records


# ── Ingestion ─────────────────────────────────────────────────────────────────

def ingest(records: list[dict], persist_path: str, google_api_key: str, dry_run: bool) -> None:
    """Upsert all records into the ChromaDB collection."""

    if dry_run:
        logger.info("[DRY-RUN] Would ingest %d documents. No changes made.", len(records))
        smell_dist: dict[str, int] = {}
        for r in records:
            smell_dist[r["smell_id"]] = smell_dist.get(r["smell_id"], 0) + 1
        for smell_id, count in sorted(smell_dist.items()):
            labels = [r["label"] for r in records if r["smell_id"] == smell_id]
            pos = labels.count("positive")
            neg = labels.count("negative")
            logger.info("  %-50s  total=%3d  pos=%3d  neg=%3d", smell_id, count, pos, neg)
        return

    from src.vectordb.chroma_client import CustomGeminiEmbeddingFunction, EMBEDDING_MODEL
    import chromadb

    ef = CustomGeminiEmbeddingFunction(
        api_key=google_api_key,
        model_name=EMBEDDING_MODEL,
    )
    client = chromadb.PersistentClient(path=persist_path)
    collection = client.get_or_create_collection(
        name="clj_smells",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    BATCH_SIZE = 50      # Google embedding API handles up to 100 at a time
    total = len(records)
    ingested = 0

    for i in range(0, total, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        collection.upsert(
            ids       = [r["id"]       for r in batch],
            documents = [r["document"] for r in batch],
            metadatas = [{
                "smell_id"         : r["smell_id"],
                "label"            : r["label"],
                "source"           : r["source"],
                "origin_type"      : r["origin_type"],
                "project"          : r["project"],
                "file_name"        : r["file_name"],
                "target_element"   : r["target_element"],
                "reasoning"        : r["reasoning"],
                "reasoning_verdict": r["reasoning_verdict"],
            } for r in batch],
        )
        ingested += len(batch)
        logger.info("Upserted %d / %d documents…", ingested, total)

    logger.info(
        "✅  Ingestion complete. Collection '%s' now has %d documents.",
        "clj_smells",
        collection.count(),
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest clj-smells-dataset into ChromaDB.")
    p.add_argument(
        "--dataset-path",
        default="../clj-smells-dataset",
        help="Path to the clj-smells-dataset root directory (default: ../clj-smells-dataset)",
    )
    p.add_argument(
        "--persist-path",
        default=".chromadb",
        help="Directory where ChromaDB persists data (default: .chromadb)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be ingested without writing to ChromaDB.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    dataset_path = Path(args.dataset_path).resolve()
    persist_path = str(Path(args.persist_path).resolve())

    logger.info("Dataset root : %s", dataset_path)
    logger.info("ChromaDB path: %s", persist_path)

    # ── Collect ──────────────────────────────────────────────────────────────
    jsonl_path  = dataset_path / "exports" / "rag_chunks_draft.jsonl"
    smells_dir  = dataset_path / "smells"

    real_records     = collect_real_curated(jsonl_path)
    catalog_records  = collect_catalog_synthetic(smells_dir)
    all_records      = real_records + catalog_records

    if not all_records:
        logger.error("No records to ingest. Exiting.")
        sys.exit(1)

    logger.info(
        "Total to ingest: %d  (real_curated=%d, catalog_synthetic=%d)",
        len(all_records), len(real_records), len(catalog_records),
    )

    # ── Ingest ───────────────────────────────────────────────────────────────
    if not args.dry_run:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        google_api_key = os.getenv("GOOGLE_API_KEY", "")
        if not google_api_key:
            logger.error("GOOGLE_API_KEY not set. Export it or add to .env")
            sys.exit(1)
    else:
        google_api_key = ""

    ingest(all_records, persist_path, google_api_key, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
