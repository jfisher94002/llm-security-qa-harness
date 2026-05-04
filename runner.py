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


def placeholder_model(prompt: str) -> str:
    """Stub until a real model is wired in."""
    return f"[placeholder] {prompt.strip()}"


def matches(actual: str, expected: str) -> bool:
    return expected in actual


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise SystemExit("test_cases.json must be a JSON array")

    rows = []
    failed = []
    for c in cases:
        cid = str(c["id"])
        prompt = c["prompt"]
        expected = c["expected"]
        actual = placeholder_model(prompt)
        ok = matches(actual, expected)
        rows.append((cid, prompt, expected, actual, ok))
        if not ok:
            failed.append(
                {"id": cid, "prompt": prompt, "expected": expected, "actual": actual}
            )

    with RUN_LOG.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "prompt", "expected", "actual", "pass"])
        for row in rows:
            w.writerow([row[0], row[1], row[2], row[3], str(row[4]).lower()])

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
