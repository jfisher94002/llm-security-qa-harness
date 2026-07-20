#!/usr/bin/env python3
"""
LLM-03 Supply Chain QA Harness — Tiered Runner.

Runs the established course tiers in order:
    Tier 1: static checks, including dependency and license scans
    Tier 2: asset identity and SHA-256/signature verification
    Tier 3: behavioral baseline comparison

Exit codes:
    0 = passed, including recorded non-critical CVE warnings
    1 = human review required
    2 = deterministic hard block
    3 = invalid configuration or tool failure
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


EXIT_PASS = 0
EXIT_REVIEW = 1
EXIT_HARD_BLOCK = 2
EXIT_INVALID = 3


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def read_json_if_exists(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        return None


def run(cmd, label):
    print(f"\n{'-' * 60}")
    print(f"Running: {label}")
    print(f"{'-' * 60}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def result_label(exit_code):
    return {
        EXIT_PASS: "passed",
        EXIT_REVIEW: "review_required",
        EXIT_HARD_BLOCK: "hard_block",
        EXIT_INVALID: "invalid_configuration_or_tool_failure",
    }.get(exit_code, "invalid_configuration_or_tool_failure")


def tier_record(tier, name, exit_code, artifact_dir=None, artifacts=None):
    return {
        "tier": tier,
        "name": name,
        "result": result_label(exit_code),
        "exit_code": exit_code,
        "artifact_dir": artifact_dir,
        "artifacts": artifacts or {},
    }


def write_review_gate(output_dir, gate_result, tier_artifact=None):
    if gate_result["exit_code"] != EXIT_REVIEW:
        return None
    review_items = []
    if tier_artifact:
        for key in ("review_required", "review_items"):
            value = tier_artifact.get(key)
            if isinstance(value, list):
                review_items.extend(value)
        for key in ("findings", "restricted_findings", "results"):
            for item in tier_artifact.get(key, []) or []:
                if item.get("disposition") == "review_required" or item.get("result") == "FAIL":
                    review_items.append(item)
    path = os.path.join(output_dir, "review_gate.json")
    write_json(path, {
        "gate": gate_result["gate"],
        "result": "review_required",
        "timestamp": now_utc(),
        "stopped_at": gate_result.get("stopped_at"),
        "review_items": review_items,
        "instructions": "Human approval is required before this gate can proceed.",
    })
    return path


def finalize(output_dir, gate_result, exit_code, stopped_at=None, tier_artifact=None):
    gate_result["exit_code"] = exit_code
    gate_result["result"] = result_label(exit_code)
    gate_result["stopped_at"] = stopped_at
    gate_result["completed_at"] = now_utc()
    if exit_code == EXIT_REVIEW:
        gate_result["review_gate"] = write_review_gate(output_dir, gate_result, tier_artifact)
    path = os.path.join(output_dir, "gate_result.json")
    gate_result["artifacts"]["gate_result"] = path
    write_json(path, gate_result)
    print("\n" + "=" * 60)
    print(f"HARNESS RESULT: {gate_result['result'].upper()} | Gate: {gate_result['gate']}")
    print(f"Artifact: {path}")
    sys.exit(exit_code)


def require_tier3_config(args, output_dir, gate_result):
    missing = []
    if not args.model:
        missing.append("--model")
    if not args.baseline:
        missing.append("--baseline")
    if missing:
        gate_result["configuration_errors"] = [f"{', '.join(missing)} required for {args.gate} gate"]
        finalize(output_dir, gate_result, EXIT_INVALID, "configuration")


def main():
    parser = argparse.ArgumentParser(description="LLM-03 tiered supply chain harness")
    parser.add_argument("--gate", choices=["pre-merge", "pre-deploy", "release"],
                        default="pre-merge", help="Which gate to run")
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--model-file", help="Path to local model file for hash check")
    parser.add_argument("--manifest", default="llm03/release_manifest.json")
    parser.add_argument("--model", help="Ollama model tag for behavioral tests")
    parser.add_argument("--baseline", default="llm03/tier3_behavioral/baseline.json")
    parser.add_argument("--prompts", default="llm03/tier3_behavioral/prompts.json")
    parser.add_argument("--output", default="llm03/sample_outputs")
    parser.add_argument("--record-baseline", action="store_true",
                        help="Record a new behavioral baseline and exit")
    parser.add_argument("--pip-audit-json", help="Offline pip-audit JSON fixture for Tier 1")
    parser.add_argument("--vulnerability-policy", default="llm03/policies/vulnerability_severity.json")
    parser.add_argument("--license-inventory-json",
                        help="Target dependency license inventory JSON for Tier 1")
    parser.add_argument("--license-exceptions", default="llm03/policies/license_exceptions.json")
    parser.add_argument("--signature-file", help="Detached Ed25519 signature file in hex for Tier 2")
    parser.add_argument("--public-key-file", help="Ed25519 public key file in hex for Tier 2")
    parser.add_argument("--public-key-hex", help="Ed25519 public key as hex for Tier 2")
    parser.add_argument("--current-responses-json",
                        help="Offline Tier 3 current-response fixture; skips live probe execution")
    args = parser.parse_args()

    ts = timestamp()
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    gate_result = {
        "gate": args.gate,
        "started_at": now_utc(),
        "tier_order": ["tier1_static"] if args.gate == "pre-merge" else [
            "tier1_static", "tier2_identity", "tier3_behavioral"
        ],
        "tiers": [],
        "artifacts": {},
    }

    print("=" * 60)
    print(f"LLM-03 Supply Chain Harness | Gate: {args.gate}")
    print(f"Timestamp: {ts}")
    print("=" * 60)

    if args.record_baseline:
        if not args.model:
            gate_result["configuration_errors"] = ["--model is required to record a baseline"]
            finalize(output_dir, gate_result, EXIT_INVALID, "configuration")
        code = run(
            ["python3", "llm03/tier3_behavioral/run_probes.py",
             "--model", args.model,
             "--prompts", args.prompts,
             "--output", args.baseline],
            "Recording behavioral baseline",
        )
        finalize(output_dir, gate_result, code if code in (0, 3) else EXIT_INVALID, "record_baseline")

    if not args.license_inventory_json:
        gate_result["configuration_errors"] = [
            "--license-inventory-json is required so Tier 1 evaluates the target dependency environment"
        ]
        finalize(output_dir, gate_result, EXIT_INVALID, "configuration")

    tier1_output = os.path.join(output_dir, f"tier1_{ts}")
    tier1_cmd = [
        "python3", "llm03/tier1_static/run_tier1.py",
        "--requirements", args.requirements,
        "--output", tier1_output,
        "--vulnerability-policy", args.vulnerability_policy,
        "--license-inventory-json", args.license_inventory_json,
        "--license-exceptions", args.license_exceptions,
    ]
    if args.pip_audit_json:
        tier1_cmd.extend(["--pip-audit-json", args.pip_audit_json])
    tier1_code = run(tier1_cmd, "Tier 1: Static code checks")
    tier1_artifacts = {
        "dependency_scan": os.path.join(tier1_output, "dep_scan.json"),
        "license_scan": os.path.join(tier1_output, "license_scan.json"),
        "tier_result": os.path.join(tier1_output, "tier1_result.json"),
    }
    gate_result["tiers"].append(tier_record(1, "tier1_static", tier1_code, tier1_output, tier1_artifacts))
    if tier1_code != EXIT_PASS:
        tier_artifact = read_json_if_exists(tier1_artifacts["tier_result"])
        finalize(output_dir, gate_result, tier1_code, "tier1_static", tier_artifact)

    if args.gate == "pre-merge":
        finalize(output_dir, gate_result, EXIT_PASS)

    if not args.model_file:
        gate_result["configuration_errors"] = [f"--model-file is required for {args.gate} gate"]
        finalize(output_dir, gate_result, EXIT_INVALID, "configuration")
    require_tier3_config(args, output_dir, gate_result)

    tier2_output = os.path.join(output_dir, f"tier2_{ts}")
    tier2_cmd = [
        "python3", "llm03/tier2_identity/run_tier2.py",
        "--model-file", args.model_file,
        "--manifest", args.manifest,
        "--output", tier2_output,
    ]
    if args.signature_file:
        tier2_cmd.extend(["--signature-file", args.signature_file])
    if args.public_key_file:
        tier2_cmd.extend(["--public-key-file", args.public_key_file])
    if args.public_key_hex:
        tier2_cmd.extend(["--public-key-hex", args.public_key_hex])
    tier2_code = run(tier2_cmd, "Tier 2: Asset identity check")
    tier2_artifacts = {
        "asset_identity": os.path.join(tier2_output, "hash_check.json"),
    }
    gate_result["tiers"].append(tier_record(2, "tier2_identity", tier2_code, tier2_output, tier2_artifacts))
    if tier2_code != EXIT_PASS:
        tier_artifact = read_json_if_exists(tier2_artifacts["asset_identity"])
        finalize(output_dir, gate_result, tier2_code, "tier2_identity", tier_artifact)

    if args.current_responses_json:
        current_path = args.current_responses_json
        probe_code = EXIT_PASS
    else:
        current_path = os.path.join(output_dir, f"current_{ts}.json")
        probe_code = run(
            ["python3", "llm03/tier3_behavioral/run_probes.py",
             "--model", args.model,
             "--prompts", args.prompts,
             "--output", current_path],
            "Tier 3: Running behavioral probes",
        )

    tier3_output = os.path.join(output_dir, f"tier3_{ts}")
    tier3_artifacts = {
        "current_responses": current_path,
        "comparison": os.path.join(tier3_output, "results.json"),
    }
    if probe_code != EXIT_PASS:
        gate_result["tiers"].append(tier_record(
            3, "tier3_behavioral_probe", EXIT_INVALID, tier3_output, tier3_artifacts
        ))
        finalize(output_dir, gate_result, EXIT_INVALID, "tier3_behavioral_probe")

    compare_code = run(
        ["python3", "llm03/tier3_behavioral/compare_responses.py",
         "--baseline", args.baseline,
         "--current", current_path,
         "--prompts", args.prompts,
         "--output", tier3_artifacts["comparison"]],
        "Tier 3: Comparing against baseline",
    )
    gate_result["tiers"].append(tier_record(3, "tier3_behavioral", compare_code, tier3_output, tier3_artifacts))
    if compare_code != EXIT_PASS:
        tier_artifact = read_json_if_exists(tier3_artifacts["comparison"])
        finalize(output_dir, gate_result, compare_code, "tier3_behavioral", tier_artifact)

    finalize(output_dir, gate_result, EXIT_PASS)


if __name__ == "__main__":
    main()
