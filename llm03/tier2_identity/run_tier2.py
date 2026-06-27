#!/usr/bin/env python3
"""
LLM-03 Tier 2: Asset Identity Layer
Verifies the SHA-256 hash of a local model file against the approved release manifest.
Exits 0 on match, 1 on mismatch or missing manifest entry.

Usage:
    python3 llm03/tier2_identity/run_tier2.py --model-file ./model.safetensors --manifest llm03/release_manifest.json
    python3 llm03/tier2_identity/run_tier2.py --model-file ./model.safetensors --manifest llm03/release_manifest.json --output ./results
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


def compute_sha256(file_path, chunk_size=65536):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(manifest_path):
    with open(manifest_path) as f:
        return json.load(f)


def find_manifest_entry(manifest, file_name):
    for entry in manifest.get("models", []):
        if entry.get("file_name") == file_name:
            return entry
    return None


def main():
    parser = argparse.ArgumentParser(description="LLM-03 Tier 2: Asset identity check")
    parser.add_argument("--model-file", required=True, help="Path to local model file to verify")
    parser.add_argument("--manifest", default="llm03/release_manifest.json", help="Path to release manifest")
    parser.add_argument("--output", default="llm03/sample_outputs/tier2", help="Output directory for artifacts")
    args = parser.parse_args()

    print("=" * 60)
    print("LLM-03 Tier 2: Asset Identity Layer")
    print("=" * 60)

    if not os.path.exists(args.model_file):
        print(f"FAIL — Model file not found: {args.model_file}")
        sys.exit(1)

    if not os.path.exists(args.manifest):
        print(f"FAIL — Manifest not found: {args.manifest}")
        sys.exit(1)

    file_name = os.path.basename(args.model_file)
    file_size = os.path.getsize(args.model_file)

    print(f"\n[TIER 2] Hash verification: {file_name}")
    print(f"  Computing SHA-256...")
    actual_hash = compute_sha256(args.model_file)

    manifest = load_manifest(args.manifest)
    entry = find_manifest_entry(manifest, file_name)

    artifact = {
        "check": "hash_verification",
        "tool": "hashlib sha256",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_file": args.model_file,
        "file_name": file_name,
        "file_size_bytes": file_size,
        "actual_hash": actual_hash,
        "expected_hash": entry.get("sha256") if entry else None,
        "manifest_entry_found": entry is not None,
        "match": False
    }

    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, "hash_check.json")

    if not entry:
        print(f"  FAIL — No manifest entry found for: {file_name}")
        print(f"  Add an approved entry to {args.manifest} before deployment.")
        artifact["result"] = "FAIL_NO_ENTRY"
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        print(f"  Artifact: {out_path}")
        sys.exit(1)

    expected_hash = entry.get("sha256", "")

    if expected_hash == "REPLACE_WITH_ACTUAL_SHA256_HASH":
        print(f"  FAIL — Manifest entry for {file_name} has not been populated with a real hash.")
        print(f"  Compute the hash from the approved artifact and update {args.manifest}.")
        artifact["result"] = "FAIL_PLACEHOLDER_HASH"
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        sys.exit(1)

    match = actual_hash == expected_hash
    artifact["match"] = match
    artifact["result"] = "PASS" if match else "FAIL_HASH_MISMATCH"

    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)

    if match:
        print(f"  PASS — Hash matches manifest entry.")
        print(f"  SHA-256: {actual_hash}")
        print(f"  Artifact: {out_path}")
        print("\n" + "=" * 60)
        print("TIER 2 RESULT: PASS — Proceed to Tier 3")
        sys.exit(0)
    else:
        print(f"  FAIL — Hash mismatch.")
        print(f"  Expected: {expected_hash}")
        print(f"  Actual:   {actual_hash}")
        print(f"  Artifact: {out_path}")
        print("\n" + "=" * 60)
        print("TIER 2 RESULT: FAIL — Do not proceed to Tier 3")
        print("Resolve artifact identity before running behavioral tests.")
        sys.exit(1)


if __name__ == "__main__":
    main()
