"""
ChromaDB client for the Clojure smell detection pipeline.

Embedding model: GoogleGenerativeAiEmbeddingFunction (text-embedding-004)

Collection schema
─────────────────
Each document stored is a Clojure code snippet (the code_content field).

Metadata per document
│  smell_id      : str   — canonical smell identifier
│  label         : str   — "positive" | "negative"
│  source        : str   — "real_curated" | "catalog_synthetic"
│  origin_type   : str   — "real" | "synthetic"
│  project       : str   — source project name (e.g. "babashka")
│  file_name     : str   — clean filename (e.g. "[babashka]__classpath.clj")
│  target_element: str   — function/namespace targeted by the smell
│  reasoning     : str   — human-edited or LLM-generated explanation (may be empty)
│  reasoning_verdict: str— "accurate" | "inaccurate" | "pending"

Queries filter by smell_id so the critic always gets examples of the
specific smell it is evaluating — not generic Clojure snippets.
"""

from __future__ import annotations

import logging
from typing import Optional

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from google import genai

from .base import VectorDBClient, ContextPackage, CodeExample

logger = logging.getLogger(__name__)

COLLECTION_NAME = "clj_smells"
EMBEDDING_MODEL  = "models/gemini-embedding-001"

import time

class CustomGeminiEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str, model_name: str = EMBEDDING_MODEL):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        retries = 3
        for attempt in range(retries):
            try:
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=list(input)
                )
                return [res.values for res in response.embeddings]
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower() or "RESOURCE_EXHAUSTED" in str(e):
                    if attempt < retries - 1:
                        logger.warning("Rate limit hit during embedding. Sleeping for 60 seconds before retrying...")
                        time.sleep(60)
                    else:
                        raise e
                else:
                    raise e


class ChromaVectorDBClient(VectorDBClient):
    """
    Persistent ChromaDB client backed by Google's embedding model.

    Parameters
    ----------
    persist_path : str
        Directory where ChromaDB will persist its data (SQLite + index).
    google_api_key : str
        Google API key used for generating embeddings.
    top_k : int
        Default number of results returned per label bucket (positive / negative).
    """

    def __init__(
        self,
        persist_path: str,
        google_api_key: str,
        top_k: int = 3,
    ) -> None:
        self._top_k = top_k

        self._ef = CustomGeminiEmbeddingFunction(
            api_key=google_api_key,
            model_name=EMBEDDING_MODEL,
        )

        self._client = chromadb.PersistentClient(path=persist_path)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            "ChromaVectorDBClient ready — collection '%s' has %d documents.",
            COLLECTION_NAME,
            self._collection.count(),
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def query(
        self,
        smell_id: str,
        snippet: str,
        top_k: Optional[int] = None,
    ) -> ContextPackage:
        """
        Retrieve evidence for a candidate smell.

        The query vector is the suspicious snippet itself (so that
        semantically similar real/synthetic smelly or clean code surfaces).

        Returns a ContextPackage with examples split by label:
          • pkg.examples["positive"]  — code WITH the smell (TP demonstrations)
          • pkg.examples["negative"]  — clean code WITHOUT the smell (FP guards)
          • pkg.examples["docs"]      — anything else
        """
        k = top_k or self._top_k
        pkg = ContextPackage(smell_id=smell_id)

        n_docs = self._collection.count()
        if n_docs == 0:
            logger.warning("ChromaDB collection is empty — run ingest_chromadb.py first.")
            return pkg

        # Query more than needed; we'll bucket by label afterwards
        fetch_n = min(k * 4, n_docs)

        try:
            results = self._collection.query(
                query_texts=[snippet],
                n_results=fetch_n,
                where={"smell_id": smell_id},
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("ChromaDB query failed for smell_id=%s: %s", smell_id, exc)
            return pkg

        docs      = results["documents"][0]       # list[str]
        metadatas = results["metadatas"][0]        # list[dict]
        distances = results["distances"][0]        # list[float] (cosine distance)

        pos_budget = k
        neg_budget = max(k // 2, 1)               # always include at least 1 clean example

        for doc, meta, dist in zip(docs, metadatas, distances):
            label      = meta.get("label", "positive")
            label_key  = label if label in pkg.examples else "docs"
            if label_key == "survey_comment":
                label_key = "survey_comments"

            # Respect per-label budget
            if label_key == "positive" and len(pkg.examples["positive"]) >= pos_budget:
                continue
            if label_key == "negative" and len(pkg.examples["negative"]) >= neg_budget:
                continue

            example = CodeExample(
                code=doc,
                label=label,
                source=meta.get("source", ""),
                description=meta.get("reasoning") or meta.get("description") or None,
            )
            pkg.examples[label_key].append(example)

        logger.debug(
            "smell_id=%s → %d positive, %d negative examples retrieved.",
            smell_id,
            len(pkg.examples["positive"]),
            len(pkg.examples["negative"]),
        )
        return pkg

    # ── Utility ───────────────────────────────────────────────────────────────

    def count(self) -> int:
        """Return the total number of documents in the collection."""
        return self._collection.count()

    def collection_stats(self) -> dict:
        """Return basic stats useful for debugging."""
        return {
            "total_documents": self._collection.count(),
            "collection_name": COLLECTION_NAME,
            "embedding_model": EMBEDDING_MODEL,
        }
