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


def normalize_evaluator_config(
    evaluator: dict[str, Any] | list[str] | None,
    fallback_indicators: list[str] | None = None,
) -> dict[str, Any]:
    if isinstance(evaluator, list):
        mode = "contains_any"
        indicators = evaluator
    elif evaluator is None:
        mode = "contains_any"
        indicators = fallback_indicators
    elif isinstance(evaluator, dict):
        mode = evaluator.get("mode", "contains_any")
        indicators = evaluator.get("failure_indicators", fallback_indicators)
    else:
        raise ValueError("evaluator must be an object")

    if not isinstance(mode, str) or mode not in SUPPORTED_MODES:
        allowed = ", ".join(sorted(SUPPORTED_MODES))
        raise ValueError(f"evaluator mode must be one of: {allowed}")

    if not isinstance(indicators, list) or not indicators:
        raise ValueError("failure_indicators must be a non-empty list")
    for item_index, item in enumerate(indicators):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"failure_indicators[{item_index}] must be a non-empty string"
            )
        if mode == "regex":
            try:
                re.compile(item)
            except re.error as exc:
                raise ValueError(
                    f"failure_indicators[{item_index}] invalid regex: {exc}"
                ) from None

    return {"mode": mode, "failure_indicators": indicators}


def find_failure_indicators(response: str, indicators: list[str]) -> list[str]:
    """Return configured indicators found in the response, case-insensitively."""
    response_lower = response.lower()
    return [item for item in indicators if item.lower() in response_lower]


def evaluate_response(response: str, evaluator: dict[str, Any] | list[str]) -> EvaluationResult:
    config = normalize_evaluator_config(evaluator)
    mode = config["mode"]
    indicators = config["failure_indicators"]

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
            if re.search(pattern, response, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        ]
        return EvaluationResult(passed=not matched, matched_indicators=matched)

    raise ValueError(f"unsupported evaluator mode: {mode}")
