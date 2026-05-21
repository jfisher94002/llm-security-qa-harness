#!/usr/bin/env python3
"""Run LLM security QA cases and write reports."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from .evaluators import evaluate_response
    from .evaluators import SUPPORTED_MODES
    from .models import load_adapter
    from .reporting import utc_now, write_reports
except ImportError:
    from evaluators import evaluate_response
    from evaluators import SUPPORTED_MODES
    from models import load_adapter
    from reporting import utc_now, write_reports

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_DIR = ROOT / "test_cases"
DEFAULT_OUTPUT_DIR = ROOT / "sample_outputs"

REQUIRED_FIELDS = {
    "id",
    "owasp_id",
    "category",
    "title",
    "severity",
    "prompt",
    "expected_safe_behavior",
}


def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases)
    adapter = load_adapter(args.config)
    started_at = utc_now()
    run_id = started_at.replace(" UTC", "Z").replace(" ", "T").replace(":", "")

    records: list[dict[str, Any]] = []
    for case in cases:
        rendered_prompt = render_prompt(case)
        for repeat_index in range(1, args.runs + 1):
            response = adapter.generate(rendered_prompt)
            result = evaluate_response(response, case["evaluator"])
            records.append(
                {
                    "run_id": run_id,
                    "timestamp_utc": utc_now(),
                    "case_id": case["id"],
                    "owasp_id": case["owasp_id"],
                    "category": case["category"],
                    "title": case["title"],
                    "severity": case["severity"],
                    "repeat_index": repeat_index,
                    "adapter": adapter.name,
                    "model": adapter.model,
                    "pass": result.passed,
                    "evaluator_mode": case["evaluator"]["mode"],
                    "matched_indicators": result.matched_indicators,
                    "asset_path": case.get("asset_path", ""),
                    "prompt_template": case["prompt"],
                    "rendered_prompt": rendered_prompt,
                    "expected_safe_behavior": case["expected_safe_behavior"],
                    "response": response,
                }
            )

    write_reports(records, args.output, started_at)
    failed = sum(1 for record in records if not record["pass"])
    print(
        f"Ran {len(records)} case run(s) with adapter={adapter.name}; "
        f"{failed} failure(s). Reports written to {args.output}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASE_DIR,
        help="Directory or JSON file containing test cases.",
    )
    parser.add_argument(
        "--runs",
        type=positive_int,
        default=1,
        help="Number of times to run each case.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for run_log.csv, failures.json, and summary.md.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional simple YAML adapter config. Defaults to mock adapter.",
    )
    return parser.parse_args()


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be 1 or greater")
    return parsed


def load_cases(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        files = sorted(path.rglob("*.json"))
    else:
        files = [path]
    if not files:
        raise SystemExit(f"{path}: no JSON test cases found")

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for file_path in files:
        raw_cases = load_case_file(file_path)
        for index, raw in enumerate(raw_cases):
            case = validate_case(raw, file_path, index)
            if case["id"] in seen_ids:
                raise SystemExit(f"{file_path}: duplicate case id '{case['id']}'")
            seen_ids.add(case["id"])
            cases.append(case)
    return cases


def load_case_file(path: Path) -> list[Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"{path}: could not read file ({exc})") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{path}: invalid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})"
        ) from None

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise SystemExit(f"{path}: root must be a JSON object or array")


def validate_case(raw: Any, path: Path, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SystemExit(f"{path}: case[{index}] must be an object")
    missing = sorted(REQUIRED_FIELDS - set(raw))
    if missing:
        raise SystemExit(f"{path}: case[{index}] missing fields: {', '.join(missing)}")

    case = dict(raw)
    for field in REQUIRED_FIELDS:
        if not isinstance(case[field], str) or not case[field].strip():
            raise SystemExit(f"{path}: case[{index}] '{field}' must be a non-empty string")

    case["evaluator"] = normalize_evaluator(case, path, index)
    case["failure_indicators"] = case["evaluator"]["failure_indicators"]

    if "asset_path" in case:
        validate_asset_path(case["asset_path"], path, index)
    if "tags" in case and (
        not isinstance(case["tags"], list)
        or not all(isinstance(tag, str) for tag in case["tags"])
    ):
        raise SystemExit(f"{path}: case[{index}] tags must be a list of strings")
    return case


def normalize_evaluator(case: dict[str, Any], path: Path, index: int) -> dict[str, Any]:
    raw_evaluator = case.get("evaluator")
    if raw_evaluator is None:
        mode = "contains_any"
        indicators = case.get("failure_indicators")
    else:
        if not isinstance(raw_evaluator, dict):
            raise SystemExit(f"{path}: case[{index}] evaluator must be an object")
        mode = raw_evaluator.get("mode", "contains_any")
        indicators = raw_evaluator.get("failure_indicators", case.get("failure_indicators"))

    if not isinstance(mode, str) or mode not in SUPPORTED_MODES:
        allowed = ", ".join(sorted(SUPPORTED_MODES))
        raise SystemExit(f"{path}: case[{index}] evaluator mode must be one of: {allowed}")

    if not isinstance(indicators, list) or not indicators:
        raise SystemExit(f"{path}: case[{index}] failure_indicators must be a non-empty list")
    for item_index, item in enumerate(indicators):
        if not isinstance(item, str) or not item.strip():
            raise SystemExit(
                f"{path}: case[{index}] failure_indicators[{item_index}] must be a non-empty string"
            )
        if mode == "regex":
            try:
                re.compile(item)
            except re.error as exc:
                raise SystemExit(
                    f"{path}: case[{index}] failure_indicators[{item_index}] invalid regex: {exc}"
                ) from None

    return {"mode": mode, "failure_indicators": indicators}


def render_prompt(case: dict[str, Any]) -> str:
    prompt = case["prompt"]
    asset_path = case.get("asset_path")
    if not asset_path:
        return prompt

    resolved = resolve_asset_path(asset_path)
    try:
        asset_content = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"{resolved}: could not read asset ({exc})") from None
    return prompt.replace("{asset_content}", asset_content)


def validate_asset_path(asset_path: Any, path: Path, index: int) -> None:
    if not isinstance(asset_path, str) or not asset_path.strip():
        raise SystemExit(f"{path}: case[{index}] asset_path must be a non-empty string")
    try:
        resolve_asset_path(asset_path)
    except ValueError as exc:
        raise SystemExit(f"{path}: case[{index}] invalid asset_path ({exc})") from None


def resolve_asset_path(asset_path: str) -> Path:
    candidate = Path(asset_path)
    if candidate.is_absolute():
        raise ValueError("absolute paths are not allowed")

    assets_root = (ROOT / "test_assets").resolve()
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(assets_root)
    except ValueError:
        raise ValueError("path must stay under test_assets/") from None
    return resolved


if __name__ == "__main__":
    main()
