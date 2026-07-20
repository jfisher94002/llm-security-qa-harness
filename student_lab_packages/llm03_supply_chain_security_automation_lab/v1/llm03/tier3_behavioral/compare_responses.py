#!/usr/bin/env python3
"""
LLM-03 Tier 3: Behavioral Layer — Response Comparator
Compares a current run artifact against a recorded baseline.

Exit codes:
    0 = passed
    1 = human review required because behavioral drift was detected
    3 = invalid configuration or tool failure

Usage:
    python3 llm03/tier3_behavioral/compare_responses.py \
        --baseline llm03/tier3_behavioral/baseline.json \
        --current llm03/tier3_behavioral/current.json \
        --prompts llm03/tier3_behavioral/prompts.json \
        --output llm03/sample_outputs/tier3/results.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


EXIT_PASS = 0
EXIT_REVIEW = 1
EXIT_INVALID = 3


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_refusal(response, failure_keywords):
    response_lower = response.lower()
    triggered = [kw for kw in failure_keywords if kw.lower() in response_lower]
    return len(triggered) == 0, triggered


def check_keyword_match(response, required_keywords):
    response_lower = response.lower()
    missing = [kw for kw in required_keywords if kw.lower() not in response_lower]
    return len(missing) == 0, missing


def main():
    parser = argparse.ArgumentParser(description="LLM-03 Tier 3: Response comparator")
    parser.add_argument("--baseline", required=True, help="Path to baseline run artifact")
    parser.add_argument("--current", required=True, help="Path to current run artifact")
    parser.add_argument("--prompts", default="llm03/tier3_behavioral/prompts.json", help="Path to prompts file")
    parser.add_argument("--output", default="llm03/sample_outputs/tier3/results.json", help="Output path for comparison results")
    args = parser.parse_args()

    for path in [args.baseline, args.current, args.prompts]:
        if not os.path.exists(path):
            print(f"File not found: {path}")
            sys.exit(EXIT_INVALID)

    try:
        baseline = load_json(args.baseline)
        current = load_json(args.current)
        prompt_data = load_json(args.prompts)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON input: {exc}")
        sys.exit(EXIT_INVALID)

    prompt_map = {p["id"]: p for p in prompt_data.get("prompts", [])}
    baseline_map = {r["id"]: r for r in baseline.get("results", [])}
    current_map = {r["id"]: r for r in current.get("results", [])}

    print("=" * 60)
    print("LLM-03 Tier 3: Behavioral Comparison")
    print(f"Baseline model:  {baseline.get('model')}  ({baseline.get('timestamp', '')[:10]})")
    print(f"Current model:   {current.get('model')}  ({current.get('timestamp', '')[:10]})")
    print("=" * 60)

    results = []
    all_pass = True

    for prompt_id, prompt_def in prompt_map.items():
        baseline_result = baseline_map.get(prompt_id)
        current_result = current_map.get(prompt_id)

        if not baseline_result or not current_result:
            print(f"\n  {prompt_id}: SKIP — missing from baseline or current run")
            continue

        check_type = prompt_def.get("check_type", "refusal")
        current_response = current_result.get("response", "")
        baseline_response = baseline_result.get("response", "")

        if check_type == "refusal":
            failure_keywords = prompt_def.get("failure_keywords", [])
            passed, triggered = check_refusal(current_response, failure_keywords)
            detail = f"Triggered keywords: {triggered}" if not passed else "No failure keywords found"

        elif check_type == "keyword_match":
            required_keywords = prompt_def.get("required_keywords", [])
            passed, missing = check_keyword_match(current_response, required_keywords)
            detail = f"Missing keywords: {missing}" if not passed else "All required keywords found"

        else:
            passed = False
            detail = f"Unknown check type: {check_type}"
            all_pass = False

        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False

        print(f"\n  {prompt_id}: {status}")
        print(f"    Check type: {check_type}")
        print(f"    {detail}")

        results.append({
            "id": prompt_id,
            "check_type": check_type,
            "result": status,
            "detail": detail,
            "baseline_response_length": len(baseline_response),
            "current_response_length": len(current_response),
            "baseline_model": baseline.get("model"),
            "current_model": current.get("model")
        })

    overall = "PASS" if all_pass else "REVIEW_REQUIRED"
    artifact = {
        "overall_result": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "baseline_model": baseline.get("model"),
        "current_model": current.get("model"),
        "checks_run": len(results),
        "checks_passed": sum(1 for r in results if r["result"] == "PASS"),
        "checks_failed": sum(1 for r in results if r["result"] == "FAIL"),
        "results": results
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(artifact, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"TIER 3 RESULT: {overall}")
    print(f"Passed: {artifact['checks_passed']} / {artifact['checks_run']}")
    print(f"Artifact: {args.output}")

    sys.exit(EXIT_PASS if all_pass else EXIT_REVIEW)


if __name__ == "__main__":
    main()
