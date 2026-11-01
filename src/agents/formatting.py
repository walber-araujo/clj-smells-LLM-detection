from ..vectordb.base import ContextPackage, CodeExample

LABEL_TITLES = {
    "positive": "Examples WITH the smell (problematic code)",
    "negative": "Clean code WITHOUT the smell (correct alternative)",
    "refactoring": "Refactoring examples (before → after)",
    "survey_comments": "Developer comments from the survey",
    "docs": "Technical documentation",
}


def format_example(ex: CodeExample) -> str:
    lines = [f"  Source: {ex.source}"]
    if ex.description:
        # Curator/prior-LLM reasoning for why this real example is labeled
        # the way it is (`final_reasoning`/`llm_suggested_reasoning` in the
        # dataset's JSONL export — see ExampleStore._real_curated_examples).
        # Was being fetched but silently dropped before this fix — the code
        # alone forces the critic to re-derive the same judgment call the
        # curator already made and recorded.
        lines.append(f"  Curator's reasoning: {ex.description}")
    lines.append(f"  ```clojure\n{ex.code}\n  ```")
    return "\n".join(lines)


def format_doc_index(sections: list[dict]) -> str:
    """Compact table of contents — preloaded once per run (like the smell
    catalog) so the agent sees what's available without a tool call."""
    if not sections:
        return "(no reference documents indexed)"
    lines = []
    current_doc = None
    for s in sections:
        if s["doc"] != current_doc:
            lines.append(f"**{s['doc']}**")
            current_doc = s["doc"]
        indent = "  " * (s["level"] - 1)
        tag = f" [{s['anchor']}]" if s.get("anchor") else ""
        lines.append(f"{indent}- {s['title']}{tag}")
    return "\n".join(lines)


def format_context_package(pkg: ContextPackage) -> str:
    parts = []

    if pkg.catalog_entry:
        entry = pkg.catalog_entry
        parts.append(
            f"### [{pkg.smell_id}] {entry.get('name', pkg.smell_id)}\n"
            f"**Catalog description:** {entry.get('summary', 'N/A')}"
        )
    else:
        parts.append(f"### [{pkg.smell_id}]")

    for label, examples in pkg.examples.items():
        if not examples:
            continue
        title = LABEL_TITLES.get(label, label.upper())
        parts.append(f"\n**{title}:**")
        for ex in examples:
            parts.append(format_example(ex))

    return "\n".join(parts)
