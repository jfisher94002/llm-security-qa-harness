#!/usr/bin/env python3
"""
LLM-03 Tier 3: Behavioral Layer - Response Comparator.

Compares current responses against a recorded baseline with deterministic,
standard-library checks. Each prompt must pass both its configured rule and its
baseline similarity threshold.

Exit codes:
    0 = passed
    1 = human review required because behavioral drift was detected
    3 = invalid configuration or tool failure
"""

import argparse
import difflib
import json
import os
import re
import sys
from datetime import datetime, timezone


EXIT_PASS = 0
EXIT_REVIEW = 1
EXIT_INVALID = 3
SUPPORTED_CHECK_TYPES = {"refusal", "keyword_match"}


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def load_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def invalid_results(output_path, message):
    artifact = {
        "overall_result": "INVALID_CONFIGURATION_OR_TOOL_FAILURE",
        "exit_code": EXIT_INVALID,
        "timestamp": now_utc(),
        "checks_run": 0,
        "checks_passed": 0,
        "checks_failed": 0,
        "error": message,
        "results": [],
    }
    write_json(output_path, artifact)
    print(f"ERROR - {message}")
    sys.exit(EXIT_INVALID)


def normalize_text(value):
    return re.sub(r"\s+", " ", value.strip().lower())


def similarity_score(baseline_response, current_response):
    return difflib.SequenceMatcher(
        None,
        normalize_text(baseline_response),
        normalize_text(current_response),
        autojunk=False,
    ).ratio()


def require_string_list(prompt_def, field):
    values = prompt_def.get(field, [])
    if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
        raise ValueError(f"prompt {prompt_def.get('id')}.{field} must be a list of non-empty strings")
    return values


def validate_prompt_data(data):
    if not isinstance(data, dict):
        raise ValueError("prompts file must be an object")
    prompts = data.get("prompts")
    if not isinstance(prompts, list):
        raise ValueError("prompts.prompts must be an array")
    if not prompts:
        raise ValueError("zero configured prompts")

    prompt_map = {}
    for index, prompt_def in enumerate(prompts):
        if not isinstance(prompt_def, dict):
            raise ValueError(f"prompts[{index}] must be an object")
        prompt_id = prompt_def.get("id")
        if not isinstance(prompt_id, str) or not prompt_id.strip():
            raise ValueError(f"prompts[{index}].id must be a non-empty string")
        if prompt_id in prompt_map:
            raise ValueError(f"duplicate prompt ID: {prompt_id}")
        check_type = prompt_def.get("check_type")
        if check_type not in SUPPORTED_CHECK_TYPES:
            raise ValueError(f"unknown check_type for {prompt_id}: {check_type}")
        threshold = prompt_def.get("baseline_similarity_threshold")
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            raise ValueError(f"prompt {prompt_id}.baseline_similarity_threshold must be a number")
        if threshold < 0 or threshold > 1:
            raise ValueError(f"prompt {prompt_id}.baseline_similarity_threshold must be between 0 and 1")
        if check_type == "refusal":
            require_string_list(prompt_def, "failure_keywords")
        if check_type == "keyword_match":
            require_string_list(prompt_def, "required_keywords")
        prompt_map[prompt_id] = prompt_def
    return prompt_map


def validate_result_artifact(data, label):
    if not isinstance(data, dict):
        raise ValueError(f"{label} artifact must be an object")
    results = data.get("results")
    if not isinstance(results, list):
        raise ValueError(f"{label}.results must be an array")
    result_map = {}
    for index, entry in enumerate(results):
        if not isinstance(entry, dict):
            raise ValueError(f"{label}.results[{index}] must be an object")
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise ValueError(f"{label}.results[{index}].id must be a non-empty string")
        if entry_id in result_map:
            raise ValueError(f"duplicate prompt ID in {label}: {entry_id}")
        response = entry.get("response")
        if not isinstance(response, str):
            raise ValueError(f"{label}.results[{index}].response must be a string")
        result_map[entry_id] = entry
    return result_map


def check_refusal(response, failure_keywords):
    response_lower = response.lower()
    triggered = [kw for kw in failure_keywords if kw.lower() in response_lower]
    return len(triggered) == 0, triggered


def check_keyword_match(response, required_keywords):
    response_lower = response.lower()
    missing = [kw for kw in required_keywords if kw.lower() not in response_lower]
    return len(missing) == 0, missing


def compare_prompt(prompt_id, prompt_def, baseline_result, current_result):
    check_type = prompt_def["check_type"]
    current_response = current_result["response"]
    baseline_response = baseline_result["response"]
    threshold = float(prompt_def["baseline_similarity_threshold"])

    if check_type == "refusal":
        passed, triggered = check_refusal(current_response, prompt_def.get("failure_keywords", []))
        rule_detail = "No failure keywords found" if passed else f"Triggered keywords: {triggered}"
    elif check_type == "keyword_match":
        passed, missing = check_keyword_match(current_response, prompt_def.get("required_keywords", []))
        rule_detail = "All required keywords found" if passed else f"Missing keywords: {missing}"
    else:
        raise ValueError(f"unknown check_type for {prompt_id}: {check_type}")

    score = similarity_score(baseline_response, current_response)
    drift_passed = score >= threshold
    final_passed = passed and drift_passed
    drift_detail = (
        f"Similarity {score:.4f} is at or above threshold {threshold:.4f}"
        if drift_passed
        else f"Similarity {score:.4f} is below threshold {threshold:.4f}"
    )

    return {
        "id": prompt_id,
        "check_type": check_type,
        "rule_result": "PASS" if passed else "FAIL",
        "rule_detail": rule_detail,
        "baseline_similarity_score": round(score, 4),
        "baseline_similarity_threshold": threshold,
        "drift_result": "PASS" if drift_passed else "FAIL",
        "drift_detail": drift_detail,
        "final_prompt_result": "PASS" if final_passed else "FAIL",
        "baseline_response_length": len(baseline_response),
        "current_response_length": len(current_response),
    }


def main():
    parser = argparse.ArgumentParser(description="LLM-03 Tier 3: Response comparator")
    parser.add_argument("--baseline", required=True, help="Path to baseline run artifact")
    parser.add_argument("--current", required=True, help="Path to current run artifact")
    parser.add_argument("--prompts", default="llm03/tier3_behavioral/prompts.json", help="Path to prompts file")
    parser.add_argument("--output", default="llm03/sample_outputs/tier3/results.json", help="Output path for comparison results")
    args = parser.parse_args()

    try:
        baseline = load_json(args.baseline)
        current = load_json(args.current)
        prompt_data = load_json(args.prompts)
        prompt_map = validate_prompt_data(prompt_data)
        baseline_map = validate_result_artifact(baseline, "baseline")
        current_map = validate_result_artifact(current, "current")

        print("=" * 60)
        print("LLM-03 Tier 3: Behavioral Comparison")
        print(f"Baseline model:  {baseline.get('model')}  ({str(baseline.get('timestamp', ''))[:10]})")
        print(f"Current model:   {current.get('model')}  ({str(current.get('timestamp', ''))[:10]})")
        print("=" * 60)

        results = []
        for prompt_id, prompt_def in prompt_map.items():
            if prompt_id not in baseline_map:
                raise ValueError(f"missing baseline entry for prompt: {prompt_id}")
            if prompt_id not in current_map:
                raise ValueError(f"missing current entry for prompt: {prompt_id}")
            result = compare_prompt(prompt_id, prompt_def, baseline_map[prompt_id], current_map[prompt_id])
            results.append(result)
            print(f"\n  {prompt_id}: {result['final_prompt_result']}")
            print(f"    Check type: {result['check_type']}")
            print(f"    Rule: {result['rule_detail']}")
            print(f"    Drift: {result['drift_detail']}")

        if not results:
            raise ValueError("zero completed comparisons")
    except ValueError as exc:
        invalid_results(args.output, str(exc))

    all_pass = all(result["final_prompt_result"] == "PASS" for result in results)
    overall = "PASS" if all_pass else "REVIEW_REQUIRED"
    exit_code = EXIT_PASS if all_pass else EXIT_REVIEW
    artifact = {
        "overall_result": overall,
        "exit_code": exit_code,
        "timestamp": now_utc(),
        "baseline_model": baseline.get("model"),
        "current_model": current.get("model"),
        "checks_run": len(results),
        "checks_passed": sum(1 for result in results if result["final_prompt_result"] == "PASS"),
        "checks_failed": sum(1 for result in results if result["final_prompt_result"] == "FAIL"),
        "results": results,
    }
    write_json(args.output, artifact)

    print(f"\n{'=' * 60}")
    print(f"TIER 3 RESULT: {overall}")
    print(f"Passed: {artifact['checks_passed']} / {artifact['checks_run']}")
    print(f"Artifact: {args.output}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
