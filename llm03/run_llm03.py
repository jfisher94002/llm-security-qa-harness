#!/usr/bin/env python3
"""
LLM-03 Supply Chain QA Harness — Tiered Runner
Runs Tier 1, Tier 2, and Tier 3 checks in order.
Stops at the first tier that fails.

Usage:
    # Pre-merge: Tier 1 only
    python3 llm03/run_llm03.py --gate pre-merge --requirements requirements.txt

    # Pre-deployment: Tier 1 + Tier 2
    python3 llm03/run_llm03.py --gate pre-deploy --requirements requirements.txt --model-file ./model.safetensors

    # Release gate: Full suite
    python3 llm03/run_llm03.py --gate release \
        --requirements requirements.txt \
        --model-file ./model.safetensors \
        --model llama3.2:3b \
        --baseline llm03/tier3_behavioral/baseline.json

    # Record a new baseline only
    python3 llm03/run_llm03.py --record-baseline --model llama3.2:3b
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime, timezone


def run(cmd, label):
    print(f"\n{'─' * 60}")
    print(f"Running: {label}")
    print(f"{'─' * 60}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="LLM-03 tiered supply chain harness")
    parser.add_argument("--gate", choices=["pre-merge", "pre-deploy", "release"],
                        default="pre-merge", help="Which gate to run")
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--model-file", help="Path to local model file for hash check")
    parser.add_argument("--manifest", default="llm03/release_manifest.json")
    parser.add_argument("--model", help="Ollama model tag for behavioral tests")
    parser.add_argument("--baseline", default="llm03/tier3_behavioral/baseline.json")
    parser.add_argument("--output", default="llm03/sample_outputs")
    parser.add_argument("--record-baseline", action="store_true",
                        help="Record a new behavioral baseline and exit")
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    print("=" * 60)
    print(f"LLM-03 Supply Chain Harness | Gate: {args.gate}")
    print(f"Timestamp: {ts}")
    print("=" * 60)

    # Record baseline mode
    if args.record_baseline:
        if not args.model:
            print("--model is required to record a baseline")
            sys.exit(1)
        success = run(
            ["python3", "llm03/tier3_behavioral/run_probes.py",
             "--model", args.model,
             "--output", args.baseline],
            "Recording behavioral baseline"
        )
        sys.exit(0 if success else 1)

    # Tier 1 — always runs
    tier1_output = os.path.join(args.output, f"tier1_{ts}")
    t1_pass = run(
        ["python3", "llm03/tier1_static/run_tier1.py",
         "--requirements", args.requirements,
         "--output", tier1_output],
        "Tier 1: Static code checks"
    )

    if not t1_pass:
        print("\n\nHarness stopped at Tier 1. Resolve findings before proceeding.")
        sys.exit(1)

    if args.gate == "pre-merge":
        print("\n\nPre-merge gate complete. PASS.")
        sys.exit(0)

    # Tier 2 — pre-deploy and release
    if not args.model_file:
        print("\n--model-file is required for pre-deploy and release gates")
        sys.exit(1)

    tier2_output = os.path.join(args.output, f"tier2_{ts}")
    t2_pass = run(
        ["python3", "llm03/tier2_identity/run_tier2.py",
         "--model-file", args.model_file,
         "--manifest", args.manifest,
         "--output", tier2_output],
        "Tier 2: Asset identity check"
    )

    if not t2_pass:
        print("\n\nHarness stopped at Tier 2. Resolve artifact identity before behavioral tests.")
        sys.exit(1)

    if args.gate == "pre-deploy" and not args.model:
        print("\n\nPre-deploy gate: Tier 1 and Tier 2 passed. No model specified, skipping Tier 3.")
        sys.exit(0)

    # Tier 3 — release gate or pre-deploy with model specified
    if not args.model:
        print("\n--model is required for Tier 3")
        sys.exit(1)

    current_path = os.path.join(args.output, f"current_{ts}.json")
    results_path = os.path.join(args.output, f"tier3_{ts}", "results.json")

    run(
        ["python3", "llm03/tier3_behavioral/run_probes.py",
         "--model", args.model,
         "--output", current_path],
        "Tier 3: Running behavioral probes"
    )

    t3_pass = run(
        ["python3", "llm03/tier3_behavioral/compare_responses.py",
         "--baseline", args.baseline,
         "--current", current_path,
         "--output", results_path],
        "Tier 3: Comparing against baseline"
    )

    print("\n" + "=" * 60)
    if t3_pass:
        print(f"HARNESS RESULT: PASS | Gate: {args.gate}")
        sys.exit(0)
    else:
        print(f"HARNESS RESULT: FAIL | Gate: {args.gate}")
        print("Behavioral drift detected. Investigate before release.")
        sys.exit(1)


if __name__ == "__main__":
    main()
