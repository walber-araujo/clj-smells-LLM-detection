import json

import pytest

from src.tools.example_lookup import ExampleStore


@pytest.fixture
def dataset(tmp_path):
    """Build a minimal clj-smells-dataset layout:
    smells/<category>/<smell_id>/{example_bad_N,example_good_N}.md
    exports/rag_chunks_draft.jsonl
    docs/*.md
    """
    root = tmp_path / "clj-smells-dataset"
    smell_dir = root / "smells" / "concurrency" / "nested_atoms"
    smell_dir.mkdir(parents=True)

    (smell_dir / "example_bad_1.md").write_text(
        "# Bad\n```clojure\n(def x (atom {:y (atom 1)}))\n```\n", encoding="utf-8"
    )
    (smell_dir / "example_bad_2.md").write_text(
        "# Bad 2\n```clojure\n(def z (atom {:w (atom 2)}))\n```\n", encoding="utf-8"
    )
    (smell_dir / "example_good_1.md").write_text(
        "# Good\n```clojure\n(def x (atom {:y 1}))\n```\n", encoding="utf-8"
    )
    # Too short after extraction -> should be skipped by the <10 char guard.
    (smell_dir / "example_bad_tiny.md").write_text(
        "# Tiny\n```clojure\n(x)\n```\n", encoding="utf-8"
    )

    exports = root / "exports"
    exports.mkdir()
    jsonl_path = exports / "rag_chunks_draft.jsonl"
    lines = [
        {
            "id": "real-1", "smell_id": "nested_atoms", "smell_verdict": "confirmed",
            "code_content": "(def a (atom {:b (atom 1)}))", "project": "proj-a",
            "final_reasoning": "curator note",
        },
        {
            "id": "real-2", "smell_id": "nested_atoms", "smell_verdict": "confirmed",
            "code_content": "(def c (atom {:d (atom 2)}))", "project": "proj-b",
        },
        {
            # pending -> must never be surfaced
            "id": "real-pending", "smell_id": "nested_atoms", "smell_verdict": "pending",
            "code_content": "(def e (atom {:f (atom 3)}))", "project": "proj-c",
        },
        {
            # different smell_id -> must never be surfaced for nested_atoms lookups
            "id": "other-smell", "smell_id": "unrelated_smell", "smell_verdict": "confirmed",
            "code_content": "(defn f [] 1)", "project": "proj-d",
        },
    ]
    jsonl_path.write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")

    docs_dir = root / "docs"
    docs_dir.mkdir()
    (docs_dir / "style-guide.md").write_text(
        "\n".join([
            "# Clojure Style Guide",
            "",
            "## Namespaces [#namespaces]",
            "Prefer require over use.",
            "",
            "### Refer all [#refer-all]",
            ":refer :all is acceptable as warranted.",
            "",
            "## Naming",
            "Use kebab-case.",
            "",
            "```clojure",
            "# this looks like a heading but is inside a fence",
            "```",
        ]),
        encoding="utf-8",
    )
    (docs_dir / "README.md").write_text("# Not indexed on purpose\n", encoding="utf-8")

    return root


def test_get_examples_prefers_real_curated_and_tops_up_with_synthetic(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    pkg = store.get_examples("nested_atoms")

    positive_sources = [ex.source for ex in pkg.examples["positive"]]
    assert positive_sources[:2] == ["real_curated:proj-a", "real_curated:proj-b"]
    # cap is 3 positives: 2 real + 1 synthetic to fill the remaining slot
    assert len(pkg.examples["positive"]) == 3
    assert positive_sources[2].startswith("catalog_synthetic:")

    # negative slot is always synthetic (real-curated has no negatives)
    assert len(pkg.examples["negative"]) == 1
    assert pkg.examples["negative"][0].source.startswith("catalog_synthetic:")


def test_get_examples_never_returns_pending_or_other_smell_ids(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    pkg = store.get_examples("nested_atoms")
    ids = {ex.id for ex in pkg.examples["positive"]}
    assert "real-pending" not in ids
    assert "other-smell" not in ids


def test_get_examples_skips_examples_shorter_than_ten_chars(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    pkg = store.get_examples("nested_atoms", exclude_ids=frozenset({"real-1", "real-2"}))
    sources = [ex.source for ex in pkg.examples["positive"]]
    assert not any("tiny" in s for s in sources)


def test_get_examples_exclude_ids_returns_next_unseen_batch(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    first = store.get_examples("nested_atoms")
    seen_ids = frozenset(ex.id for exs in first.examples.values() for ex in exs if ex.id)

    second = store.get_examples("nested_atoms", exclude_ids=seen_ids)
    second_ids = {ex.id for exs in second.examples.values() for ex in exs if ex.id}
    assert second_ids.isdisjoint(seen_ids)


def test_get_examples_unknown_smell_id_returns_empty_package(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    pkg = store.get_examples("no_such_smell")
    assert all(len(v) == 0 for v in pkg.examples.values())


def test_count_available_is_not_bounded_by_the_per_call_cap(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    counts = store.count_available("nested_atoms")
    # Unlike get_examples(), count_available uses unbounded budgets, so it
    # reports the full real+synthetic total uncapped: 2 real-curated
    # positives + both synthetic positives (bad_1, bad_2 — bad_tiny is
    # still excluded, it's under the 10-char minimum regardless of budget).
    assert counts["positive"] == 4
    assert counts["negative"] == 1


def test_known_smell_ids_lists_directory_names(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    assert store.known_smell_ids() == ["nested_atoms"]


def test_list_doc_sections_indexes_headings_and_skips_readme(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    sections = store.list_doc_sections()
    docs = {s["doc"] for s in sections}
    assert docs == {"style-guide.md"}
    titles = [s["title"] for s in sections]
    assert "Namespaces" in titles
    assert "Refer all" in titles
    assert "Naming" in titles


def test_list_doc_sections_ignores_headings_inside_code_fences(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    sections = store.list_doc_sections()
    titles = [s["title"] for s in sections]
    assert not any("this looks like a heading" in t for t in titles)


def test_get_doc_section_matches_by_anchor(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    text = store.get_doc_section("style-guide.md", "namespaces")
    assert "Prefer require over use." in text
    # Section stops at the next heading of the SAME level, so its nested
    # subsection (### Refer all) is included in the parent's span.
    assert "Refer all" in text


def test_get_doc_section_matches_by_title(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    text = store.get_doc_section("style-guide.md", "Naming")
    assert "Use kebab-case." in text
    assert "Refer all" not in text


def test_get_doc_section_falls_back_to_bracket_parsing(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    # Model pastes the whole displayed line "Title [anchor]" back verbatim.
    text = store.get_doc_section("style-guide.md", "Refer all [#refer-all]")
    assert ":refer :all is acceptable as warranted." in text


def test_get_doc_section_unknown_doc_returns_error_string(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    result = store.get_doc_section("no-such-doc.md", "anything")
    assert "No such doc" in result


def test_get_doc_section_unknown_section_returns_error_string(dataset):
    store = ExampleStore(dataset_path=str(dataset))
    result = store.get_doc_section("style-guide.md", "nonexistent-section")
    assert "No section matching" in result


def test_example_store_missing_directories_logs_warning_but_does_not_raise(tmp_path, caplog):
    empty_root = tmp_path / "empty"
    store = ExampleStore(dataset_path=str(empty_root))
    assert store.get_examples("anything").examples["positive"] == []
    assert store.list_doc_sections() == []
    assert store.known_smell_ids() == []
