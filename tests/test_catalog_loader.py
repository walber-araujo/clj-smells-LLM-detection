import json

import pytest

from src.catalog.loader import format_catalog_for_prompt, load_catalog


def _write_catalog(tmp_path, categories):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"categories": categories}), encoding="utf-8")
    return path


def test_load_catalog_flattens_categories_into_smell_id_index(tmp_path):
    path = _write_catalog(tmp_path, [
        {
            "label": "Concurrency",
            "smells": [
                {"id": "nested_atoms", "name": "Nested Atoms", "summary": "atom in an atom"},
            ],
        },
        {
            "label": "Laziness",
            "smells": [
                {"id": "unnecessary_laziness", "name": "Unnecessary Laziness", "summary": "map then vec"},
            ],
        },
    ])

    catalog = load_catalog(str(path))

    assert set(catalog.keys()) == {"nested_atoms", "unnecessary_laziness"}
    assert catalog["nested_atoms"] == {
        "id": "nested_atoms", "name": "Nested Atoms",
        "summary": "atom in an atom", "category": "Concurrency",
    }
    assert catalog["unnecessary_laziness"]["category"] == "Laziness"


def test_load_catalog_raises_file_not_found_error(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError):
        load_catalog(str(missing))


def test_format_catalog_for_prompt_renders_one_bullet_per_smell():
    catalog = {
        "a": {"id": "a", "name": "A", "summary": "summary a", "category": "Cat"},
        "b": {"id": "b", "name": "B", "summary": "summary b", "category": "Cat"},
    }
    text = format_catalog_for_prompt(catalog)
    assert text == "- [a] summary a\n- [b] summary b"


def test_format_catalog_for_prompt_empty_catalog_returns_empty_string():
    assert format_catalog_for_prompt({}) == ""
