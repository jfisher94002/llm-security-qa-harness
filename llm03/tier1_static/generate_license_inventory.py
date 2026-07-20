#!/usr/bin/env python3
"""Generate the target license inventory consumed by LLM-03 Tier 1."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


EXIT_PASS = 0
EXIT_INVALID = 3
TIMEOUT_SECONDS = 120


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_pip_licenses():
    try:
        result = subprocess.run(
            ["pip-licenses", "--format", "json", "--with-license-file", "--no-license-path"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise ValueError(
            "pip-licenses executable not found. Install it in the active target "
            "environment with: python3 -m pip install pip-licenses"
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"pip-licenses timed out after {exc.timeout} seconds")
    except OSError as exc:
        raise ValueError(f"pip-licenses could not be launched: {exc}")

    if result.returncode != 0:
        raise ValueError(f"pip-licenses exited {result.returncode}: {result.stderr.strip()[:500]}")
    try:
        packages = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"pip-licenses returned invalid JSON: {exc}")
    if not isinstance(packages, list):
        raise ValueError("pip-licenses JSON output must be a package list")
    return packages


def normalize_packages(packages):
    normalized = []
    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            raise ValueError(f"pip-licenses package[{index}] must be an object")
        normalized.append({
            "Name": str(package.get("Name", "")),
            "Version": str(package.get("Version", "")),
            "License": str(package.get("License", "")),
        })
    return normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", default="requirements.txt",
                        help="Target requirements file installed in the active environment")
    parser.add_argument("--output", default="target_license_inventory.json",
                        help="Output inventory JSON path")
    args = parser.parse_args()

    try:
        requirements_path = Path(args.requirements)
        if not requirements_path.exists():
            raise ValueError(f"requirements file not found: {args.requirements}")
        packages = normalize_packages(run_pip_licenses())
        inventory = {
            "source": "active target Python environment",
            "generated_at": now_utc(),
            "requirements_file": requirements_path.name,
            "requirements_sha256": sha256_file(requirements_path),
            "generator": "llm03/tier1_static/generate_license_inventory.py",
            "python_version": sys.version.split()[0],
            "packages": packages,
        }
        write_json(args.output, inventory)
        print(f"License inventory written to {args.output}")
        sys.exit(EXIT_PASS)
    except ValueError as exc:
        error_artifact = {
            "result": "invalid_configuration_or_tool_failure",
            "exit_code": EXIT_INVALID,
            "timestamp": now_utc(),
            "requirements_file": Path(args.requirements).name,
            "generator": "llm03/tier1_static/generate_license_inventory.py",
            "error": str(exc),
        }
        write_json(args.output, error_artifact)
        print(f"ERROR — {exc}")
        sys.exit(EXIT_INVALID)


if __name__ == "__main__":
    main()
