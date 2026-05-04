#!/usr/bin/env python3
"""Minimal QA harness: JSON cases → placeholder model → substring checks → reports."""

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

_REQUIRED_FIELDS = ("id", "prompt", "expected")


def placeholder_model(prompt: str) -> str:
    """Stub until a real model is wired in."""
    return f"[placeholder] {prompt.strip()}"


def matches(actual: str, expected: str) -> bool:
    return expected in actual


def _parse_case(raw: object, index: int) -> tuple[str, str, str, bool]:
    if not isinstance(raw, dict):
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] must be an object, not {type(raw).__name__}"
        )
    missing = [f for f in _REQUIRED_FIELDS if f not in raw]
    if missing:
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] missing required field(s): {', '.join(missing)}"
        )
    cid_raw, prompt, expected = raw["id"], raw["prompt"], raw["expected"]
    if not isinstance(cid_raw, (str, int)):
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] 'id' must be a string or integer, "
            f"not {type(cid_raw).__name__}"
        )
    if not isinstance(prompt, str):
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] 'prompt' must be a string, "
            f"not {type(prompt).__name__}"
        )
    if not isinstance(expected, str):
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] 'expected' must be a string, "
            f"not {type(expected).__name__}"
        )
    xfail = raw.get("xfail", False)
    if not isinstance(xfail, bool):
        raise SystemExit(
            f"{CASES_PATH}: case[{index}] 'xfail' must be a boolean, "
            f"not {type(xfail).__name__}"
        )
    return str(cid_raw), prompt, expected, xfail


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
        cid, prompt, expected, xfail = _parse_case(raw, i)
        actual = placeholder_model(prompt)
        substr_ok = matches(actual, expected)
        harness_ok = (substr_ok and not xfail) or (not substr_ok and xfail)
        rows.append((cid, prompt, expected, actual, xfail, substr_ok, harness_ok))
        if not harness_ok:
            reason = "unexpected_pass" if xfail and substr_ok else "mismatch"
            failed.append(
                {
                    "id": cid,
                    "prompt": prompt,
                    "expected": expected,
                    "actual": actual,
                    "xfail": xfail,
                    "reason": reason,
                }
            )

    with RUN_LOG.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["id", "prompt", "expected", "actual", "xfail", "substring_match", "pass"]
        )
        for row in rows:
            w.writerow(
                [
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    str(row[4]).lower(),
                    str(row[5]).lower(),
                    str(row[6]).lower(),
                ]
            )

    FAILURES.write_text(
        json.dumps(failed, indent=2) + "\n",
        encoding="utf-8",
    )

    n = len(rows)
    passed = n - len(failed)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    SUMMARY.write_text(
        "\n".join(
            [
                "# Run summary",
                "",
                f"- **When:** {ts}",
                f"- **Cases:** {n}",
                f"- **Passed:** {passed}",
                f"- **Failed:** {len(failed)}",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
