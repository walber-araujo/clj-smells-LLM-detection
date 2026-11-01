import pytest

from src.artifact.validator import (
    MalformedOutputError,
    _extract_json,
    parse_critic_output,
    parse_detection_output,
)


# ── _extract_json ────────────────────────────────────────────────────────────

def test_extract_json_strips_markdown_fence_with_language_tag():
    raw = '```json\n{"a": 1}\n```'
    assert _extract_json(raw) == '{"a": 1}'


def test_extract_json_strips_bare_markdown_fence():
    raw = '```\n[1, 2, 3]\n```'
    assert _extract_json(raw) == "[1, 2, 3]"


def test_extract_json_picks_earliest_bracket_when_object_precedes_array():
    raw = 'noise {"a": [1, 2]} trailing'
    assert _extract_json(raw) == '{"a": [1, 2]}'


def test_extract_json_picks_earliest_bracket_when_array_precedes_object():
    raw = 'noise [{"a": 1}] trailing'
    assert _extract_json(raw) == '[{"a": 1}]'


def test_extract_json_balances_nested_braces():
    raw = 'prefix {"a": {"b": {"c": 1}}} suffix'
    assert _extract_json(raw) == '{"a": {"b": {"c": 1}}}'


def test_extract_json_returns_cleaned_text_when_no_json_present():
    assert _extract_json("no json here") == "no json here"


# ── parse_detection_output ───────────────────────────────────────────────────

def test_parse_detection_output_accepts_bare_array():
    raw = '[{"smell_id": "a"}, {"smell_id": "b", "element_name": "f"}]'
    candidates = parse_detection_output(raw)
    assert [c.smell_id for c in candidates] == ["a", "b"]
    assert candidates[1].element_name == "f"


def test_parse_detection_output_accepts_candidates_wrapper():
    raw = '{"candidates": [{"smell_id": "a"}]}'
    assert parse_detection_output(raw)[0].smell_id == "a"


def test_parse_detection_output_accepts_smells_wrapper():
    raw = '{"smells": [{"smell_id": "a"}]}'
    assert parse_detection_output(raw)[0].smell_id == "a"


def test_parse_detection_output_accepts_single_bare_object():
    raw = '{"smell_id": "a"}'
    assert parse_detection_output(raw)[0].smell_id == "a"


def test_parse_detection_output_defaults_to_empty_list_for_unknown_wrapper_keys():
    raw = '{"unexpected": []}'
    assert parse_detection_output(raw) == []


def test_parse_detection_output_raises_on_invalid_json():
    with pytest.raises(MalformedOutputError):
        parse_detection_output("not json at all {")


def test_parse_detection_output_raises_when_not_a_list_or_dict():
    with pytest.raises(MalformedOutputError):
        parse_detection_output("42")


def test_parse_detection_output_raises_on_schema_mismatch():
    with pytest.raises(MalformedOutputError):
        parse_detection_output('[{"no_smell_id_field": true}]')


def test_parse_detection_output_strips_markdown_fence():
    raw = '```json\n[{"smell_id": "a"}]\n```'
    assert parse_detection_output(raw)[0].smell_id == "a"


# ── parse_critic_output ──────────────────────────────────────────────────────

def _verdict_json(**overrides):
    base = {
        "smell_id": "x", "element_name": "f", "confirmed": True,
        "confidence": "high", "reasoning": "matches the pattern",
        "evidence_used": ["src1"],
    }
    base.update(overrides)
    return base


def test_parse_critic_output_accepts_bare_array():
    import json
    raw = json.dumps([_verdict_json()])
    verdicts = parse_critic_output(raw)
    assert verdicts[0].smell_id == "x"
    assert verdicts[0].confirmed is True
    assert verdicts[0].evidence_used == ["src1"]


def test_parse_critic_output_accepts_verdicts_wrapper():
    import json
    raw = json.dumps({"verdicts": [_verdict_json()]})
    assert parse_critic_output(raw)[0].smell_id == "x"


def test_parse_critic_output_accepts_results_wrapper():
    import json
    raw = json.dumps({"results": [_verdict_json()]})
    assert parse_critic_output(raw)[0].smell_id == "x"


def test_parse_critic_output_accepts_single_bare_object():
    import json
    raw = json.dumps(_verdict_json())
    assert parse_critic_output(raw)[0].smell_id == "x"


def test_parse_critic_output_raises_on_invalid_confidence():
    import json
    raw = json.dumps([_verdict_json(confidence="super-high")])
    with pytest.raises(MalformedOutputError):
        parse_critic_output(raw)


def test_parse_critic_output_raises_when_confirmed_missing():
    import json
    bad = _verdict_json()
    del bad["confirmed"]
    with pytest.raises(MalformedOutputError):
        parse_critic_output(json.dumps([bad]))


def test_parse_critic_output_error_message_includes_raw_snippet():
    try:
        parse_critic_output("{not json")
    except MalformedOutputError as exc:
        assert "not json" in str(exc)
    else:
        pytest.fail("expected MalformedOutputError")
