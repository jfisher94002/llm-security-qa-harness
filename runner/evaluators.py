"""Basic response evaluators for the starter harness."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SUPPORTED_MODES = {"contains_any", "contains_all", "regex"}


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    matched_indicators: list[str]


def find_failure_indicators(response: str, indicators: list[str]) -> list[str]:
    """Return configured indicators found in the response, case-insensitively."""
    response_lower = response.lower()
    return [item for item in indicators if item.lower() in response_lower]


def evaluate_response(response: str, evaluator: dict[str, Any] | list[str]) -> EvaluationResult:
    if isinstance(evaluator, list):
        mode = "contains_any"
        indicators = evaluator
    else:
        mode = evaluator["mode"]
        indicators = evaluator["failure_indicators"]

    if mode == "contains_any":
        matched = find_failure_indicators(response, indicators)
        return EvaluationResult(passed=not matched, matched_indicators=matched)

    if mode == "contains_all":
        matched = find_failure_indicators(response, indicators)
        return EvaluationResult(
            passed=len(matched) != len(indicators),
            matched_indicators=matched if len(matched) == len(indicators) else [],
        )

    if mode == "regex":
        matched = [
            pattern
            for pattern in indicators
            if re.search(pattern, response, flags=re.IGNORECASE | re.MULTILINE)
        ]
        return EvaluationResult(passed=not matched, matched_indicators=matched)

    raise ValueError(f"unsupported evaluator mode: {mode}")
