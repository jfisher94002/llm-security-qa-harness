#!/usr/bin/env python3
"""LLM security QA harness: test cases → placeholder model → failure-indicator checks → reports."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "test_cases.json"
OUT_DIR = ROOT / "sample_outputs"
RUN_LOG = OUT_DIR / "run_log.csv"
FAILURES = OUT_DIR / "failures.json"
SUMMARY = OUT_DIR / "summary.md"

_REQUIRED_FIELDS = (
    "id",
    "category",
    "title",
    "prompt",
    "failure_indicators",
    "expected_safe_behavior",
    "severity",
)


def placeholder_model(prompt: str) -> str:
    """Stub until a real model API is wired in."""
    return f"[placeholder] {prompt.strip()}"


def indicators_hit(response: str, indicators: list[str]) -> list[str]:
    return [s for s in indicators if s in response]


def _parse_case(raw: object, index: int) -> dict:
    if not isinstance(raw, dict):
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] must be an object, not {type(raw).__name__}"
        )
    missing = [f for f in _REQUIRED_FIELDS if f not in raw]
    if missing:
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] missing required field(s): {', '.join(missing)}"
        )

    cid = raw["id"]
    if not isinstance(cid, (str, int)):
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] 'id' must be a string or integer, "
            f"not {type(cid).__name__}"
        )

    out: dict = {"id": str(cid)}
    for key in ("category", "title", "prompt", "expected_safe_behavior", "severity"):
        val = raw[key]
        if not isinstance(val, str):
            raise SystemExit(
                f"{CASES_PATH}: case[{index}] '{key}' must be a string, "
                f"not {type(val).__name__}"
            )
        out[key] = val

    fi = raw["failure_indicators"]
    if not isinstance(fi, list) or not fi:
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] 'failure_indicators' must be a non-empty JSON array"
        )
    indicators: list[str] = []
    for j, item in enumerate(fi):
        if not isinstance(item, str) or not item:
            raise SystemExit(
                f"{CASES_PATH}: case[{index}] failure_indicators[{j}] must be a non-empty string"
            )
        indicators.append(item)
    out["failure_indicators"] = indicators
    return out


def _load_cases() -> list:
    try:
        text = CASES_PATH.read_text(encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"{CASES_PATH}: could not read file ({e})") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"{CASES_PATH}: invalid JSON ({e.msg} at line {e.lineno}, column {e.colno})"
        ) from None
    if not isinstance(data, list):
        raise SystemExit(f"{CASES_PATH}: root value must be a JSON array")
    return data


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = _load_cases()

    rows = []
    failed = []
    for i, raw in enumerate(cases):
        c = _parse_case(raw, i)
        response = placeholder_model(c["prompt"])
        matched = indicators_hit(response, c["failure_indicators"])
        passed = len(matched) == 0
        rows.append(
            {
                **c,
                "response": response,
                "matched_indicators": matched,
                "pass": passed,
            }
        )
        if not passed:
            failed.append(
                {
                    "id": c["id"],
                    "category": c["category"],
                    "title": c["title"],
                    "severity": c["severity"],
                    "prompt": c["prompt"],
                    "response": response,
                    "matched_indicators": matched,
                    "expected_safe_behavior": c["expected_safe_behavior"],
                }
            )

    with RUN_LOG.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "id",
                "category",
                "title",
                "severity",
                "pass",
                "matched_indicators",
                "prompt",
                "response",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r["id"],
                    r["category"],
                    r["title"],
                    r["severity"],
                    str(r["pass"]).lower(),
                    "; ".join(r["matched_indicators"]),
                    r["prompt"],
                    r["response"],
                ]
            )

    FAILURES.write_text(
        json.dumps(failed, indent=2) + "\n",
        encoding="utf-8",
    )

    n = len(rows)
    passed_n = n - len(failed)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    SUMMARY.write_text(
        "\n".join(
            [
                "# Run summary",
                "",
                f"- **When:** {ts}",
                f"- **Cases:** {n}",
                f"- **Passed:** {passed_n}",
                f"- **Failed:** {len(failed)}",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
