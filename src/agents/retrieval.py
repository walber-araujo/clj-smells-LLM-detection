import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..vectordb.base import VectorDBClient, ContextPackage
from ..artifact.schema import CandidateSmell

logger = logging.getLogger(__name__)

class Retriever:
    """Pure Python fan-out over the vector DB — no LLM involved at all,
    so definitely not an agent. Used only in --retrieval rag mode."""

    def __init__(self, vectordb: VectorDBClient, catalog: dict):
        self.vectordb = vectordb
        self.catalog = catalog

    def run(
        self,
        candidates: list[CandidateSmell],
        top_k: int = 3,
    ) -> tuple[list[ContextPackage], float]:
        """
        Returns (list[ContextPackage], total_latency_ms).
        Queries are dispatched concurrently — one thread per candidate smell.
        Since each query uses a different smell_id filter, they are fully independent.
        """
        start = time.time()

        if not candidates:
            return [], (time.time() - start) * 1000

        def _query_one(candidate: CandidateSmell) -> ContextPackage:
            pkg = self.vectordb.query(
                smell_id=candidate.smell_id,
                snippet=candidate.snippet or "",
                top_k=top_k,
            )
            if candidate.smell_id in self.catalog:
                pkg.catalog_entry = self.catalog[candidate.smell_id]
            total_examples = sum(len(exs) for exs in pkg.examples.values())
            logger.info(
                "Retrieved %d examples for smell '%s' from VectorDB",
                total_examples, candidate.smell_id,
            )
            return pkg

        # Parallelise: one thread per candidate (I/O-bound ChromaDB calls)
        with ThreadPoolExecutor(max_workers=min(len(candidates), 8)) as executor:
            future_to_idx = {
                executor.submit(_query_one, cand): i
                for i, cand in enumerate(candidates)
            }
            packages: list[ContextPackage | None] = [None] * len(candidates)
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                packages[idx] = future.result()

        latency_ms = (time.time() - start) * 1000
        return packages, latency_ms
