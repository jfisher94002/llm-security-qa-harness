"""Report writers for harness results."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_LOG = "run_log.csv"
FAILURES = "failures.json"
SUMMARY = "summary.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def write_reports(records: list[dict[str, Any]], output_dir: Path, started_at: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_run_log(records, output_dir / RUN_LOG)
    _write_failures(records, output_dir / FAILURES)
    _write_summary(records, output_dir / SUMMARY, started_at)


def _write_run_log(records: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "run_id",
        "timestamp_utc",
        "case_id",
        "owasp_id",
        "category",
        "title",
        "severity",
        "repeat_index",
        "adapter",
        "model",
        "pass",
        "evaluator_mode",
        "matched_indicators",
        "asset_path",
        "prompt_template",
        "rendered_prompt",
        "response",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    key: "; ".join(record[key])
                    if key == "matched_indicators"
                    else record.get(key, "")
                    for key in fields
                }
            )


def _write_failures(records: list[dict[str, Any]], path: Path) -> None:
    failures = [
        {
            "run_id": record["run_id"],
            "case_id": record["case_id"],
            "owasp_id": record["owasp_id"],
            "category": record["category"],
            "title": record["title"],
            "severity": record["severity"],
            "repeat_index": record["repeat_index"],
            "adapter": record["adapter"],
            "model": record["model"],
            "evaluator_mode": record["evaluator_mode"],
            "matched_indicators": record["matched_indicators"],
            "asset_path": record["asset_path"],
            "prompt_template": record["prompt_template"],
            "rendered_prompt": record["rendered_prompt"],
            "expected_safe_behavior": record["expected_safe_behavior"],
            "response": record["response"],
        }
        for record in records
        if not record["pass"]
    ]
    path.write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")


def _write_summary(records: list[dict[str, Any]], path: Path, started_at: str) -> None:
    total = len(records)
    failed = sum(1 for record in records if not record["pass"])
    passed = total - failed
    by_owasp = Counter(record["owasp_id"] for record in records)
    failed_by_owasp = Counter(record["owasp_id"] for record in records if not record["pass"])

    lines = [
        "# Run Summary",
        "",
        f"- **Started:** {started_at}",
        f"- **Completed:** {utc_now()}",
        f"- **Total runs:** {total}",
        f"- **Passed:** {passed}",
        f"- **Failed:** {failed}",
        "",
        "## By OWASP Category",
        "",
        "| OWASP ID | Runs | Failures |",
        "| --- | ---: | ---: |",
    ]
    for owasp_id in sorted(by_owasp):
        lines.append(f"| {owasp_id} | {by_owasp[owasp_id]} | {failed_by_owasp[owasp_id]} |")

    lines.extend(
        [
            "",
            "## Security Caveat",
            "",
            "Passing tests do not prove the app is secure. These checks only show that the configured string indicators were not observed in the sampled outputs.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
