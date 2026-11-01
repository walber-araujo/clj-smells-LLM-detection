from src.vectordb.mock_client import MockVectorDBClient, _parse_dataset_example


class _EmptyRglobPath:
    """Stand-in for pathlib.Path that always reports no matching dataset
    directory, forcing MockVectorDBClient.query() down its _MOCK_DATA
    fallback path deterministically, regardless of what's on the machine
    running the tests (the real code hardcodes an absolute, machine-local
    dataset path)."""

    def __init__(self, *_a, **_kw):
        pass

    def rglob(self, _pattern):
        return []


def test_query_falls_back_to_hardcoded_mock_data_when_dataset_dir_absent(monkeypatch):
    monkeypatch.setattr("src.vectordb.mock_client.Path", _EmptyRglobPath)
    client = MockVectorDBClient()

    pkg = client.query("unmanaged_resource_io", snippet="(io/reader f)")

    assert len(pkg.examples["positive"]) == 1
    assert "with-open" not in pkg.examples["positive"][0].code  # the smelly example
    assert len(pkg.examples["negative"]) == 1
    assert "with-open" in pkg.examples["negative"][0].code
    assert len(pkg.examples["refactoring"]) == 1


def test_query_unknown_smell_id_returns_all_empty_buckets(monkeypatch):
    monkeypatch.setattr("src.vectordb.mock_client.Path", _EmptyRglobPath)
    client = MockVectorDBClient()

    pkg = client.query("totally_unknown_smell", snippet="whatever")

    assert pkg.smell_id == "totally_unknown_smell"
    assert all(len(v) == 0 for v in pkg.examples.values())


def test_query_survey_comment_label_lands_in_survey_comments_bucket(monkeypatch):
    """`_MOCK_DATA` labels entries "survey_comment" (singular); `pkg.examples`
    exposes a "survey_comments" (plural) bucket. The remap must check the
    raw `doc["label"]`, not a `label_key` already downgraded to "docs" by
    the `in pkg.examples` fallback — otherwise the remap can never fire."""
    monkeypatch.setattr("src.vectordb.mock_client.Path", _EmptyRglobPath)
    client = MockVectorDBClient()

    pkg = client.query("unmanaged_resource_io", snippet="(io/reader f)")

    assert pkg.examples["docs"] == []
    assert len(pkg.examples["survey_comments"]) == 1
    assert "Survey respondent" in pkg.examples["survey_comments"][0].source


def test_query_respects_top_k_times_five_slice(monkeypatch):
    monkeypatch.setattr("src.vectordb.mock_client.Path", _EmptyRglobPath)
    client = MockVectorDBClient()

    # nested_atoms has 3 raw docs in _MOCK_DATA; top_k=0 * 5 = 0 -> none taken.
    pkg = client.query("nested_atoms", snippet="x", top_k=0)
    assert all(len(v) == 0 for v in pkg.examples.values())


def test_parse_dataset_example_extracts_description_code_and_label(tmp_path):
    md = tmp_path / "example_good_case.md"
    md.write_text(
        "# Some smell\n"
        "* **Short explanation:** this shows the idiomatic alternative.\n\n"
        "```clojure\n(mapv f coll)\n```\n",
        encoding="utf-8",
    )
    result = _parse_dataset_example(md)
    assert result["label"] == "negative"  # "good" in filename
    assert result["description"] == "this shows the idiomatic alternative."
    assert result["code"] == "(mapv f coll)"
    assert result["source"] == f"Dataset: {md.name}"


def test_parse_dataset_example_defaults_to_positive_label():
    import pathlib
    from src.vectordb.mock_client import _parse_dataset_example as parse
    # filename with neither "good" nor "refactor" -> positive
    class _FakePath:
        name = "example_bad_1.md"
        def read_text(self, encoding=None):
            return "```clojure\n(atom (atom 1))\n```"
    result = parse(_FakePath())
    assert result["label"] == "positive"
    assert result["code"] == "(atom (atom 1))"


def test_parse_dataset_example_refactor_label():
    class _FakePath:
        name = "example_refactor_1.md"
        def read_text(self, encoding=None):
            return "```clojure\n;; before/after\n```"
    from src.vectordb.mock_client import _parse_dataset_example as parse
    assert parse(_FakePath())["label"] == "refactoring"


def test_parse_dataset_example_missing_description_is_none():
    class _FakePath:
        name = "example_bad_2.md"
        def read_text(self, encoding=None):
            return "```clojure\n(f)\n```"
    from src.vectordb.mock_client import _parse_dataset_example as parse
    assert parse(_FakePath())["description"] is None


def test_parse_dataset_example_missing_code_block_is_empty_string():
    class _FakePath:
        name = "example_bad_3.md"
        def read_text(self, encoding=None):
            return "no code block here"
    from src.vectordb.mock_client import _parse_dataset_example as parse
    assert parse(_FakePath())["code"] == ""
