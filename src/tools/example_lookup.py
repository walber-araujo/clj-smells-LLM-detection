"""
example_lookup.py — file-based, on-demand example lookup for the agentic
retrieval path.

This is the "just-in-time context" counterpart to src/vectordb/chroma_client.py.
Instead of embedding every snippet and ranking by cosine similarity, it reads
straight from the dataset's own folder-per-smell_id structure (and the
curated JSONL) at call time — the same pattern Claude Code uses (glob + read,
no pre-built index) rather than pre-loading everything into memory upfront.
Nothing is scanned until a smell_id is actually asked for.

No embedding API, no vector DB, no eager index. Meant to be exposed to the
Critic LLM as a tool it calls on demand (see src/agents/agentic_critic.py),
not pre-fetched by an orchestrator step.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..vectordb.base import ContextPackage, CodeExample

logger = logging.getLogger(__name__)


def _extract_md_code(text: str) -> str:
    match = re.search(r"```[Cc]lojure\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\n(.*?)\n```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


# The one supported convention for anything dropped into docs/: Markdown
# headings, optionally tagged with an explicit anchor — `## Title [#anchor]`.
# One format, one regex — new doc files just need to follow this to be
# indexed; see docs/README.md.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s*\[#([\w-]+)\])?\s*$")


class ExampleStore:
    """
    No upfront index. __init__ just records paths (no I/O); get_examples()
    globs the smell's own folder and scans the JSONL fresh on every call —
    reads exactly what's asked for, when it's asked for, so the cost stays
    flat no matter how large the rest of the dataset grows.
    """

    def __init__(self, dataset_path: str = "../clj-smells-dataset"):
        root = Path(dataset_path).resolve()
        self._smells_dir = root / "smells"
        self._jsonl_path = root / "exports" / "rag_chunks_draft.jsonl"
        self._docs_dir = root / "docs"

        if not self._smells_dir.exists():
            logger.warning("ExampleStore: smells directory not found: %s", self._smells_dir)
        if not self._jsonl_path.exists():
            logger.warning("ExampleStore: real-curated export not found: %s", self._jsonl_path)
        if not self._docs_dir.exists():
            logger.info("ExampleStore: no docs directory at %s — list_doc_sections()/get_doc_section() will find nothing.", self._docs_dir)

        logger.info("ExampleStore ready — will read on demand from %s (no upfront index).", root)

    def _synthetic_examples(
        self, smell_id: str, pos_budget: int, neg_budget: int,
        exclude_ids: frozenset[str] = frozenset(),
    ) -> list[CodeExample]:
        examples: list[CodeExample] = []
        pos_count = neg_count = 0

        for smell_dir in self._smells_dir.rglob(smell_id):
            if not smell_dir.is_dir():
                continue
            for md_path in sorted(smell_dir.glob("*.md")):
                name_lower = md_path.stem.lower()
                if "bad" in name_lower:
                    label = "positive"
                elif "good" in name_lower:
                    label = "negative"
                else:
                    continue
                if label == "positive" and pos_count >= pos_budget:
                    continue
                if label == "negative" and neg_count >= neg_budget:
                    continue

                ex_id = f"catalog_synthetic:{md_path.name}"
                if ex_id in exclude_ids:
                    continue

                text = md_path.read_text(encoding="utf-8")
                code = _extract_md_code(text)
                if not code or len(code) < 10:
                    continue

                examples.append(CodeExample(code=code, label=label, source=ex_id, id=ex_id))
                if label == "positive":
                    pos_count += 1
                else:
                    neg_count += 1
            break  # rglob(smell_id) — first matching directory is the smell's own folder

        return examples

    # Fixed system-level per-CALL caps, not a per-call choice by the model —
    # it has no way to know how many confirmed examples exist for a smell_id
    # before asking, so picking a number isn't its call to make. This is how
    # many NEW examples come back each time get_examples() is called for a
    # smell_id; calling it again for the same smell_id (with the
    # previously-returned ids passed as `exclude_ids`) returns the next
    # not-yet-seen batch, up to these same caps, until nothing new is left.
    # Real-curated (human-confirmed) examples are preferred and fill this
    # budget first; synthetic only tops up whatever's left. Real-curated
    # also has zero negative examples (every record in rag_chunks_draft.jsonl
    # is a confirmed *positive* instance), so the negative slot is always
    # synthetic.
    _POSITIVE_EXAMPLES_CAP = 3
    _NEGATIVE_EXAMPLES_CAP = 1

    def _real_curated_examples(
        self, smell_id: str, limit: int, exclude_ids: frozenset[str] = frozenset(),
    ) -> list[CodeExample]:
        if not self._jsonl_path.exists():
            return []

        examples: list[CodeExample] = []
        with self._jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                if len(examples) >= limit or not line.strip():
                    continue
                chunk = json.loads(line)
                if chunk.get("smell_id") != smell_id or chunk.get("smell_verdict") != "confirmed":
                    continue
                ex_id = chunk.get("id")
                if ex_id in exclude_ids:
                    continue

                code = chunk.get("code_content", "").strip() or chunk.get("full_file_code", "").strip()
                if not code:
                    continue

                examples.append(CodeExample(
                    code=code,
                    label="positive",
                    source=f"real_curated:{chunk.get('project', 'unknown')}",
                    description=chunk.get("final_reasoning") or chunk.get("llm_suggested_reasoning"),
                    id=ex_id,
                ))

        return examples

    def get_examples(self, smell_id: str, exclude_ids: frozenset[str] = frozenset()) -> ContextPackage:
        """
        No caller-supplied limit — there's nothing the caller could base one
        on (it has no way to know how many confirmed examples exist for a
        given smell_id before asking). Fixed instead:
        _POSITIVE_EXAMPLES_CAP (3) human-confirmed real examples, synthetic
        catalog examples only filling in whatever's left of that cap when
        real evidence is thin or absent; _NEGATIVE_EXAMPLES_CAP (1) synthetic
        negative, since real-curated has none.

        `exclude_ids`: ids (CodeExample.id) already returned by an earlier
        call for this smell_id this run — those are skipped, so a second
        call naturally surfaces the *next* not-yet-seen batch instead of
        repeating the first one. An empty/partial result here means there's
        genuinely nothing new left, not that anything was held back.

        Reads the filesystem/JSONL fresh on every call — nothing is cached.
        """
        pkg = ContextPackage(smell_id=smell_id)

        real = self._real_curated_examples(smell_id, self._POSITIVE_EXAMPLES_CAP, exclude_ids)
        pkg.examples["positive"].extend(real)

        remaining_pos = self._POSITIVE_EXAMPLES_CAP - len(pkg.examples["positive"])
        synthetic = self._synthetic_examples(smell_id, remaining_pos, self._NEGATIVE_EXAMPLES_CAP, exclude_ids)
        for ex in synthetic:
            pkg.examples[ex.label].append(ex)

        return pkg

    def count_available(self, smell_id: str) -> dict[str, int]:
        """True total positive/negative example count for smell_id — real
        confirmed + synthetic combined, unbounded by _POSITIVE_EXAMPLES_CAP/
        _NEGATIVE_EXAMPLES_CAP. Used to tell the agent how many examples
        exist in total (so it can judge whether calling again is worth it)
        without changing what a normal get_examples() call actually
        returns — that stays capped."""
        real = self._real_curated_examples(smell_id, limit=10**9)
        synthetic = self._synthetic_examples(smell_id, pos_budget=10**9, neg_budget=10**9)
        return {
            "positive": len(real) + sum(1 for ex in synthetic if ex.label == "positive"),
            "negative": sum(1 for ex in synthetic if ex.label == "negative"),
        }

    def known_smell_ids(self) -> list[str]:
        """Directory listing for diagnostics only — not used by the tool itself."""
        if not self._smells_dir.exists():
            return []
        return sorted({p.name for p in self._smells_dir.glob("*/*/") if p.is_dir()})

    def _doc_files(self) -> list[Path]:
        """Every .md in docs/, except README.md — that one documents the
        folder's own convention, it isn't reference content for the critic."""
        if not self._docs_dir.exists():
            return []
        return sorted(
            p for p in self._docs_dir.glob("*.md")
            if p.is_file() and p.name.lower() != "readme.md"
        )

    @staticmethod
    def _iter_headings(lines: list[str]):
        """Yield (index, level, title, anchor) for real Markdown headings only
        — skips anything inside ``` fenced code blocks, so a shell comment
        like `# Generates README.pdf` in a code sample isn't mistaken for a
        level-1 heading."""
        in_fence = False
        for i, line in enumerate(lines):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = _HEADING_RE.match(line)
            if m:
                level, title, anchor = m.groups()
                yield i, len(level), title.strip(), anchor

    def list_doc_sections(self) -> list[dict]:
        """
        Cheap table-of-contents across every file in docs/, fetched via a
        tool call on demand (D5 — reverted from preloading it directly into
        the prompt: the dataset currently has one reference doc, but this
        index is meant to grow, and a fixed per-run cost that scales with
        however many docs get added is exactly the pattern D5 already
        rejected once for the *full-content* version of this same mistake).
        """
        sections: list[dict] = []
        for doc_path in self._doc_files():
            lines = doc_path.read_text(encoding="utf-8").splitlines()
            for _, level, title, anchor in self._iter_headings(lines):
                sections.append({"doc": doc_path.name, "level": level, "title": title, "anchor": anchor})
        return sections

    def get_doc_section(self, doc_name: str, section: str) -> str:
        """
        Full text of one section — from its heading to the next heading of
        equal-or-higher level (or end of file) — matched by anchor or title
        (case-insensitive). `doc_name` and `section` should come from
        list_doc_sections()'s output.
        """
        doc_path = self._docs_dir / doc_name
        if not doc_path.exists():
            return f"No such doc: '{doc_name}'. Check the documentation index for valid names."

        lines = doc_path.read_text(encoding="utf-8").splitlines()
        needle = section.strip().lower()
        # Robustness fix, not a formatting request: list_doc_sections()
        # renders each entry as one line, "Title [anchor]" — and in
        # practice (seen twice, in two unrelated traces) the model pastes
        # that whole displayed line back as `section` instead of pulling
        # out just the anchor or just the title, which used to fail this
        # exact-match lookup and cost a wasted round-trip. If `needle` ends
        # in a `[...]` bracket, also try the bracket content (anchor) and
        # the text before it (title) as fallback matches.
        needle_candidates = [needle]
        bracket_match = re.match(r"^(.*?)\s*\[([^\]]+)\]\s*$", needle)
        if bracket_match:
            needle_candidates.append(bracket_match.group(2).strip())
            needle_candidates.append(bracket_match.group(1).strip())

        start_idx = start_level = None
        for i, level, title, anchor in self._iter_headings(lines):
            title_l, anchor_l = title.lower(), (anchor or "").lower()
            if any(c == anchor_l or c == title_l for c in needle_candidates):
                start_idx, start_level = i, level
                break

        if start_idx is None:
            return f"No section matching '{section}' found in {doc_name}. Check the documentation index for valid section names/anchors."

        end_idx = len(lines)
        for j, level, _, _ in self._iter_headings(lines):
            if j > start_idx and level <= start_level:
                end_idx = j
                break

        return "\n".join(lines[start_idx:end_idx]).strip()

