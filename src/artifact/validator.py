import json
import re
from typing import Union

from pydantic import ValidationError as PydanticValidationError

from .schema import CandidateSmell, Verdict


class MalformedOutputError(ValueError):
    """Raised when LLM output cannot be parsed into the expected schema."""
    pass


def _extract_json(raw: str) -> str:
    """
    Strip markdown code fences and extract the first JSON array or object.
    LLMs sometimes wrap their JSON in ```json ... ``` blocks.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    first_bracket = cleaned.find("[")
    first_brace = cleaned.find("{")
    
    targets = []
    if first_bracket != -1:
        targets.append((first_bracket, "[", "]"))
    if first_brace != -1:
        targets.append((first_brace, "{", "}"))
        
    if not targets:
        return cleaned
        
    start, start_char, end_char = min(targets, key=lambda x: x[0])
    
    depth = 0
    for i, ch in enumerate(cleaned[start:], start=start):
        if ch == start_char:
            depth += 1
        elif ch == end_char:
            depth -= 1
            if depth == 0:
                return cleaned[start: i + 1]
                
    return cleaned


def parse_detection_output(raw: str) -> list[CandidateSmell]:
    """
    Parse the Detector's raw LLM output into a list of CandidateSmell.
    Accepts both a bare array and a {"candidates": [...]} wrapper.
    Raises MalformedOutputError on any failure — triggers retry.
    """
    try:
        json_str = _extract_json(raw)
        data = json.loads(json_str)

        if isinstance(data, dict):
            if "smell_id" in data:
                data = [data]
            else:
                data = data.get("candidates", data.get("smells", []))

        if not isinstance(data, list):
            raise MalformedOutputError("Expected a JSON array of candidates.")

        return [CandidateSmell(**item) for item in data]

    except (json.JSONDecodeError, KeyError, TypeError, PydanticValidationError) as exc:
        raise MalformedOutputError(f"Detection output invalid: {exc}\n\nRaw:\n{raw[:500]}")


def parse_critic_output(raw: str) -> list[Verdict]:
    """
    Parse the Critic's raw LLM output into a list of Verdict.
    Accepts both a bare array and a {"verdicts": [...]} wrapper.
    Raises MalformedOutputError on any failure — triggers retry.
    """
    try:
        json_str = _extract_json(raw)
        data = json.loads(json_str)

        if isinstance(data, dict):
            if "smell_id" in data:
                data = [data]
            else:
                data = data.get("verdicts", data.get("results", []))

        if not isinstance(data, list):
            raise MalformedOutputError("Expected a JSON array of verdicts.")

        return [Verdict(**item) for item in data]

    except (json.JSONDecodeError, KeyError, TypeError, PydanticValidationError) as exc:
        raise MalformedOutputError(f"Critic output invalid: {exc}\n\nRaw:\n{raw[:500]}")
