from src.agents.formatting import format_context_package, format_doc_index, format_example
from src.vectordb.base import CodeExample, ContextPackage


def test_format_example_includes_source_and_code():
    ex = CodeExample(code="(defn f [] 1)", label="positive", source="real_curated:proj")
    text = format_example(ex)
    assert "Source: real_curated:proj" in text
    assert "(defn f [] 1)" in text
    assert "Curator's reasoning" not in text


def test_format_example_includes_description_when_present():
    ex = CodeExample(
        code="(defn f [] 1)", label="positive", source="real_curated:proj",
        description="curator says this is a real instance",
    )
    text = format_example(ex)
    assert "Curator's reasoning: curator says this is a real instance" in text


def test_format_doc_index_empty_sections():
    assert format_doc_index([]) == "(no reference documents indexed)"


def test_format_doc_index_groups_by_doc_and_indents_by_level():
    sections = [
        {"doc": "guide.md", "level": 1, "title": "Namespaces", "anchor": "namespaces"},
        {"doc": "guide.md", "level": 2, "title": "Refer all", "anchor": None},
        {"doc": "other.md", "level": 1, "title": "Naming", "anchor": None},
    ]
    text = format_doc_index(sections)
    lines = text.splitlines()
    assert lines[0] == "**guide.md**"
    assert lines[1] == "- Namespaces [namespaces]"
    assert lines[2] == "  - Refer all"
    assert lines[3] == "**other.md**"
    assert lines[4] == "- Naming"


def test_format_context_package_with_catalog_entry_and_examples():
    pkg = ContextPackage(
        smell_id="nested_atoms",
        catalog_entry={"name": "Nested Atoms", "summary": "atom in an atom"},
    )
    pkg.examples["positive"].append(
        CodeExample(code="(atom (atom 1))", label="positive", source="s1")
    )
    text = format_context_package(pkg)
    assert "### [nested_atoms] Nested Atoms" in text
    assert "**Catalog description:** atom in an atom" in text
    assert "Examples WITH the smell (problematic code):" in text
    assert "(atom (atom 1))" in text
    # empty label buckets are skipped entirely
    assert "Clean code WITHOUT the smell" not in text


def test_format_context_package_without_catalog_entry_falls_back_to_smell_id():
    pkg = ContextPackage(smell_id="nested_atoms")
    text = format_context_package(pkg)
    assert text == "### [nested_atoms]"
