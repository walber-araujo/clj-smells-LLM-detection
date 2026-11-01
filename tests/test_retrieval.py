import time

from src.agents.retrieval import Retriever
from src.artifact.schema import CandidateSmell
from src.vectordb.base import ContextPackage, VectorDBClient


class _FakeVectorDB(VectorDBClient):
    def __init__(self, delay_by_smell_id=None):
        self.delay_by_smell_id = delay_by_smell_id or {}
        self.queries = []

    def query(self, smell_id, snippet, top_k=3):
        self.queries.append((smell_id, snippet, top_k))
        time.sleep(self.delay_by_smell_id.get(smell_id, 0))
        return ContextPackage(smell_id=smell_id)


CATALOG = {"a": {"id": "a", "name": "A", "summary": "s", "category": "c"}}


def test_run_returns_one_package_per_candidate_in_original_order():
    candidates = [
        CandidateSmell(smell_id="a", element_name="f1", snippet="c1"),
        CandidateSmell(smell_id="b", element_name="f2", snippet="c2"),
        CandidateSmell(smell_id="c", element_name="f3", snippet="c3"),
    ]
    # Slower queries finish first candidates last, but result order must
    # still match `candidates`, not completion order.
    vectordb = _FakeVectorDB(delay_by_smell_id={"a": 0.05, "b": 0.0, "c": 0.02})
    retriever = Retriever(vectordb=vectordb, catalog=CATALOG)

    packages, latency_ms = retriever.run(candidates)

    assert [p.smell_id for p in packages] == ["a", "b", "c"]
    assert latency_ms >= 0


def test_run_attaches_catalog_entry_when_known():
    candidates = [CandidateSmell(smell_id="a", element_name="f1", snippet="c1")]
    vectordb = _FakeVectorDB()
    retriever = Retriever(vectordb=vectordb, catalog=CATALOG)

    packages, _ = retriever.run(candidates)

    assert packages[0].catalog_entry == CATALOG["a"]


def test_run_leaves_catalog_entry_none_when_unknown_smell_id():
    candidates = [CandidateSmell(smell_id="unknown", element_name="f1", snippet="c1")]
    vectordb = _FakeVectorDB()
    retriever = Retriever(vectordb=vectordb, catalog=CATALOG)

    packages, _ = retriever.run(candidates)

    assert packages[0].catalog_entry is None


def test_run_passes_empty_string_snippet_when_candidate_snippet_is_none():
    candidates = [CandidateSmell(smell_id="a", element_name="f1", snippet=None)]
    vectordb = _FakeVectorDB()
    retriever = Retriever(vectordb=vectordb, catalog=CATALOG)

    retriever.run(candidates)

    assert vectordb.queries[0] == ("a", "", 3)


def test_run_with_no_candidates_returns_empty_list_without_raising():
    vectordb = _FakeVectorDB()
    retriever = Retriever(vectordb=vectordb, catalog=CATALOG)

    packages, latency_ms = retriever.run([])

    assert packages == []
    assert latency_ms >= 0
    assert vectordb.queries == []
