#!/usr/bin/env python3
"""
LLM-03 Tier 1: Static Code Layer
Runs pip-audit and pip-licenses checks against the target requirements file.
Exits 0 on pass, 1 on any finding that blocks release.

Usage:
    python3 llm03/tier1_static/run_tier1.py --requirements requirements.txt
    python3 llm03/tier1_static/run_tier1.py --requirements requirements.txt --output ./results
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


RESTRICTED_LICENSES = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "GPL-2.0-only", "GPL-3.0-only", "AGPL-3.0-only"}


def run_pip_audit(requirements_file, output_dir):
    print(f"\n[TIER 1] Dependency scan: {requirements_file}")
    result = subprocess.run(
        ["pip-audit", "-r", requirements_file, "--format", "json"],
        capture_output=True, text=True
    )
    audit_output = result.stdout.strip()
    findings = []
    try:
        data = json.loads(audit_output) if audit_output else []
        for item in data:
            for vuln in item.get("vulns", []):
                findings.append({
                    "package": item.get("name"),
                    "installed_version": item.get("version"),
                    "vuln_id": vuln.get("id"),
                    "fix_versions": vuln.get("fix_versions", []),
                    "description": vuln.get("description", "")[:200]
                })
    except json.JSONDecodeError:
        # pip-audit may not return JSON on error
        pass

    artifact = {
        "check": "dependency_scan",
        "tool": "pip-audit",
        "requirements_file": requirements_file,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
        "exit_code": result.returncode,
        "raw_output": result.stdout[:4000]
    }

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "dep_scan.json")
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)

    if findings:
        print(f"  FAIL — {len(findings)} finding(s). See {out_path}")
        for f in findings:
            print(f"    {f['package']} {f['installed_version']} → {f['vuln_id']}")
        return False
    else:
        print(f"  PASS — No findings. Artifact: {out_path}")
        return True


def run_license_scan(output_dir):
    print(f"\n[TIER 1] License scan")
    result = subprocess.run(
        ["pip-licenses", "--format", "json", "--with-license-file", "--no-license-path"],
        capture_output=True, text=True
    )
    packages = []
    restricted = []
    try:
        packages = json.loads(result.stdout) if result.stdout.strip() else []
        for pkg in packages:
            lic = pkg.get("License", "")
            if any(r in lic for r in RESTRICTED_LICENSES):
                restricted.append({"package": pkg.get("Name"), "version": pkg.get("Version"), "license": lic})
    except json.JSONDecodeError:
        pass

    artifact = {
        "check": "license_scan",
        "tool": "pip-licenses",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_packages": len(packages),
        "restricted_findings": restricted,
        "restricted_licenses_checked": sorted(RESTRICTED_LICENSES)
    }

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "license_scan.json")
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)

    if restricted:
        print(f"  FAIL — {len(restricted)} restricted license(s). See {out_path}")
        for r in restricted:
            print(f"    {r['package']} {r['version']} — {r['license']}")
        return False
    else:
        print(f"  PASS — No restricted licenses. Artifact: {out_path}")
        return True


def main():
    parser = argparse.ArgumentParser(description="LLM-03 Tier 1: Static code checks")
    parser.add_argument("--requirements", default="requirements.txt", help="Path to requirements file")
    parser.add_argument("--output", default="llm03/sample_outputs/tier1", help="Output directory for artifacts")
    args = parser.parse_args()

    print("=" * 60)
    print("LLM-03 Tier 1: Static Code Layer")
    print("=" * 60)

    dep_pass = run_pip_audit(args.requirements, args.output)
    lic_pass = run_license_scan(args.output)

    print("\n" + "=" * 60)
    if dep_pass and lic_pass:
        print("TIER 1 RESULT: PASS — Proceed to Tier 2")
        sys.exit(0)
    else:
        print("TIER 1 RESULT: FAIL — Do not proceed to Tier 2")
        print("Resolve all findings before running asset identity checks.")
        sys.exit(1)


if __name__ == "__main__":
    main()
