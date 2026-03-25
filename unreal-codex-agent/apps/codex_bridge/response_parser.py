from __future__ import annotations

import ast
import json
import re
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from apps.codex_bridge.decision_schema import ActionDecision, CompletionDecision, ReviewDecision


T = TypeVar("T", bound=BaseModel)


class ResponseParseError(Exception):
    pass


def extract_json_block(text: str) -> str:
    text = text.strip()
    fenced_match = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)
    generic_fenced_match = re.search(r"```\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if generic_fenced_match:
        return generic_fenced_match.group(1)
    object_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if object_match:
        return object_match.group(1)
    raise ResponseParseError("No JSON object found in response.")


def _cleanup_json_candidate(text: str) -> str:
    cleaned = text.strip().lstrip("\ufeff")
    replacements = {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    return cleaned


def _pythonize_literals(text: str) -> str:
    converted = re.sub(r"\btrue\b", "True", text, flags=re.IGNORECASE)
    converted = re.sub(r"\bfalse\b", "False", converted, flags=re.IGNORECASE)
    converted = re.sub(r"\bnull\b", "None", converted, flags=re.IGNORECASE)
    return converted


def parse_json_object(text: str) -> dict[str, Any]:
    candidate = _cleanup_json_candidate(extract_json_block(text))
    try:
        data = json.loads(candidate)
        if not isinstance(data, dict):
            raise ResponseParseError("Top-level JSON response must be an object.")
        return data
    except json.JSONDecodeError as exc:
        try:
            data = ast.literal_eval(_pythonize_literals(candidate))
        except (ValueError, SyntaxError) as literal_exc:
            raise ResponseParseError(f"Invalid JSON returned: {exc}") from literal_exc
        if not isinstance(data, dict):
            raise ResponseParseError("Top-level JSON response must be an object.")
        return data


def parse_model(text: str, model_cls: Type[T]) -> T:
    data = parse_json_object(text)
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise ResponseParseError(f"JSON did not match expected schema: {exc}") from exc


def parse_action_response(text: str) -> ActionDecision:
    return parse_model(text, ActionDecision)


def parse_review_response(text: str) -> ReviewDecision:
    return parse_model(text, ReviewDecision)


def parse_completion_response(text: str) -> CompletionDecision:
    return parse_model(text, CompletionDecision)
