"""Basic response evaluators for the starter harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    matched_indicators: list[str]


def find_failure_indicators(response: str, indicators: list[str]) -> list[str]:
    """Return configured indicators found in the response, case-insensitively."""
    response_lower = response.lower()
    return [item for item in indicators if item.lower() in response_lower]


def evaluate_response(response: str, indicators: list[str]) -> EvaluationResult:
    matched = find_failure_indicators(response, indicators)
    return EvaluationResult(passed=not matched, matched_indicators=matched)
