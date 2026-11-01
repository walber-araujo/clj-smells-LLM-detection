from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CodeExample:
    """A single code snippet stored in the vector DB."""
    code: str
    label: str          # "positive" | "negative" | "refactoring" | "survey_comment" | "doc"
    source: str
    description: Optional[str] = None
    # Unique identifier for this specific example (e.g. the JSONL record's
    # own "id", or a synthetic file's name) — `source` alone can collide,
    # e.g. multiple confirmed real examples from the same project for the
    # same smell all share `source="real_curated:<project>"`. Used by
    # ExampleStore's already-sent tracking (agentic path) to tell examples
    # apart; not otherwise rendered to the model.
    id: Optional[str] = None


@dataclass
class ContextPackage:
    """
    All retrieved evidence for a single candidate smell.
    Assembled by the Retriever and passed as-is to the Critic.
    """
    smell_id: str
    catalog_entry: Optional[dict] = None   # filled by Retriever from catalog
    examples: dict = field(default_factory=lambda: {
        "positive": [],       # code WITH the smell
        "negative": [],       # clean code WITHOUT the smell
        "refactoring": [],    # before → after transformation
        "survey_comments": [],
        "docs": [],
    })


class VectorDBClient(ABC):
    """
    Abstract base class for vector database providers.

    The query method receives the smell_id and the suspicious snippet
    detected by the Detector, and returns a ContextPackage with
    all retrieved evidence grouped by label.
    """

    @abstractmethod
    def query(
        self,
        smell_id: str,
        snippet: str,
        top_k: int = 3,
    ) -> ContextPackage:
        """Retrieve evidence for a candidate smell from the vector DB."""
        ...
