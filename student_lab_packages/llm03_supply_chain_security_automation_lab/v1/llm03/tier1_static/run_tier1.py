#!/usr/bin/env python3
"""
LLM-03 Tier 1: Static Code Layer.

Runs dependency and license checks for the target dependency set.

Exit codes:
    0 = passed, including recorded non-critical CVE warnings
    1 = human review required
    2 = deterministic hard block
    3 = invalid configuration or tool failure

Usage:
    python3 llm03/tier1_static/run_tier1.py --requirements requirements.txt

    # Offline, reproducible lab mode
    python3 llm03/tier1_static/run_tier1.py \
        --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
        --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone


EXIT_PASS = 0
EXIT_REVIEW = 1
EXIT_HARD_BLOCK = 2
EXIT_INVALID = 3

DEFAULT_VULN_POLICY = "llm03/policies/vulnerability_severity.json"
DEFAULT_LICENSE_EXCEPTIONS = "llm03/policies/license_exceptions.json"
DEFAULT_RESTRICTED_LICENSES = {
    "GPL-2.0",
    "GPL-3.0",
    "AGPL-3.0",
    "GPL-2.0-only",
    "GPL-3.0-only",
    "AGPL-3.0-only",
}
NON_CRITICAL_SEVERITIES = {"low", "medium", "moderate", "high"}
PIP_AUDIT_TIMEOUT_SECONDS = 120
REQUIRED_INVENTORY_FIELDS = {
    "source": str,
    "generated_at": str,
    "requirements_file": str,
    "requirements_sha256": str,
    "generator": str,
    "python_version": str,
    "packages": list,
}


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def load_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise ValueError(f"file not found: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}")


def write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def normalize_vulnerability_id(value):
    return str(value or "").strip().upper()


def load_vulnerability_policy(path):
    data = load_json(path)
    severity_map = {}
    for vuln_id, details in data.get("vulnerabilities", {}).items():
        if isinstance(details, str):
            severity = details
        else:
            severity = details.get("severity")
        if severity:
            severity_map[normalize_vulnerability_id(vuln_id)] = severity.lower()
    return {
        "path": path,
        "hard_block_severities": {
            str(s).lower() for s in data.get("hard_block_severities", ["critical"])
        },
        "severity_map": severity_map,
    }


def run_pip_audit(requirements_file):
    try:
        result = subprocess.run(
            ["pip-audit", "-r", requirements_file, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=PIP_AUDIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise ValueError(
            "pip-audit executable not found. Install it in the target environment "
            "or use --pip-audit-json for offline fixture mode."
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"pip-audit timed out after {exc.timeout} seconds")
    except OSError as exc:
        raise ValueError(f"pip-audit could not be launched: {exc}")

    stdout = result.stdout.strip()
    if not stdout:
        raise ValueError(f"pip-audit returned no JSON output; exit code {result.returncode}")
    try:
        return json.loads(stdout), result.returncode, result.stdout
    except json.JSONDecodeError as exc:
        raise ValueError(f"pip-audit returned invalid JSON: {exc}")


def load_pip_audit_data(requirements_file, fixture_path):
    if fixture_path:
        return load_json(fixture_path), 0, f"loaded fixture: {fixture_path}", fixture_path
    data, exit_code, raw_output = run_pip_audit(requirements_file)
    return data, exit_code, raw_output[:4000], "pip-audit"


def iter_pip_audit_dependencies(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("dependencies"), list):
            return data["dependencies"]
        if isinstance(data.get("results"), list):
            return data["results"]
    raise ValueError("unsupported pip-audit JSON shape; expected a list or a dependencies/results object")


def extract_vuln_ids(vuln):
    ids = []
    for key in ("id", "vuln_id", "cve", "ghsa"):
        if vuln.get(key):
            ids.append(vuln[key])
    ids.extend(vuln.get("aliases", []) or [])
    normalized = []
    for item in ids:
        vuln_id = normalize_vulnerability_id(item)
        if vuln_id and vuln_id not in normalized:
            normalized.append(vuln_id)
    return normalized


def classify_dependency_findings(audit_data, policy):
    findings = []
    for item in iter_pip_audit_dependencies(audit_data):
        package = item.get("name") or item.get("package")
        version = item.get("version") or item.get("installed_version")
        for vuln in item.get("vulns", []) or []:
            vuln_ids = extract_vuln_ids(vuln)
            primary_id = vuln_ids[0] if vuln_ids else "UNKNOWN"
            mapped_severity = None
            mapped_by = None
            for vuln_id in vuln_ids:
                if vuln_id in policy["severity_map"]:
                    mapped_severity = policy["severity_map"][vuln_id]
                    mapped_by = vuln_id
                    break

            if mapped_severity in policy["hard_block_severities"]:
                disposition = "hard_block"
            elif mapped_severity in NON_CRITICAL_SEVERITIES:
                disposition = "warning"
            else:
                disposition = "review_required"

            findings.append({
                "package": package,
                "installed_version": version,
                "vuln_id": primary_id,
                "aliases": vuln_ids,
                "mapped_severity": mapped_severity or "unknown",
                "mapped_by": mapped_by,
                "disposition": disposition,
                "fix_versions": vuln.get("fix_versions", []),
                "description": (vuln.get("description") or "")[:300],
            })
    return findings


def load_license_inventory(path):
    if not path:
        raise ValueError(
            "--license-inventory-json is required so Tier 1 evaluates the target dependency environment"
        )
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("license inventory must be an object")
    for field, expected_type in REQUIRED_INVENTORY_FIELDS.items():
        if field not in data:
            raise ValueError(f"license inventory missing required field: {field}")
        if not isinstance(data[field], expected_type):
            raise ValueError(f"license inventory field '{field}' must be {expected_type.__name__}")
        if expected_type is str and not data[field].strip():
            raise ValueError(f"license inventory field '{field}' must be non-empty")
    requirements_sha = data["requirements_sha256"]
    if len(requirements_sha) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in requirements_sha):
        raise ValueError("license inventory requirements_sha256 must be a 64-character hex digest")
    packages = data["packages"]
    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            raise ValueError(f"license inventory packages[{index}] must be an object")
        for field in ("Name", "Version", "License"):
            if field not in package:
                raise ValueError(f"license inventory packages[{index}] missing required field: {field}")
            if not isinstance(package[field], str):
                raise ValueError(f"license inventory packages[{index}].{field} must be a string")
    return packages, data["source"], data


def load_license_exceptions(path):
    if not path or not os.path.exists(path):
        return []
    data = load_json(path)
    exceptions = data.get("exceptions", data if isinstance(data, list) else [])
    if not isinstance(exceptions, list):
        raise ValueError("license exceptions must be a list or an object with an exceptions list")
    for index, exception in enumerate(exceptions):
        if not isinstance(exception, dict):
            raise ValueError(f"license exceptions[{index}] must be an object")
        for field in ("package", "version", "license"):
            if not isinstance(exception.get(field), str) or not exception[field].strip():
                raise ValueError(f"license exceptions[{index}].{field} must be a non-empty string")
        expiration = exception.get("expiration")
        if expiration is not None and parse_date(expiration) is None:
            raise ValueError(f"license exceptions[{index}].expiration must use YYYY-MM-DD")
    return exceptions


def license_matches(restricted_license, restricted_licenses):
    license_text = str(restricted_license or "")
    license_upper = license_text.upper()
    return any(token.upper() in license_upper for token in restricted_licenses)


def parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def exception_matches(exception, finding):
    return (
        str(exception.get("package", "")).lower() == str(finding.get("package", "")).lower()
        and str(exception.get("version", "")) == str(finding.get("version", ""))
        and str(exception.get("license", "")).lower() == str(finding.get("license", "")).lower()
    )


def validate_exception(exception):
    approval_fields = ["approver", "reason", "ticket", "expiration"]
    missing = [field for field in approval_fields if not exception.get(field)]
    if missing:
        return False, f"exception missing approval field(s): {', '.join(missing)}"
    expiration = parse_date(exception.get("expiration"))
    if expiration is None:
        raise ValueError("exception expiration must use YYYY-MM-DD")
    if expiration < date.today():
        return False, "exception expired"
    return True, "valid exception"


def classify_license_findings(packages, exceptions, restricted_licenses):
    restricted = []
    for pkg in packages:
        name = pkg.get("Name") or pkg.get("name") or pkg.get("package")
        version = pkg.get("Version") or pkg.get("version")
        license_name = pkg.get("License") or pkg.get("license")
        if not license_matches(license_name, restricted_licenses):
            continue

        finding = {
            "package": name,
            "version": version,
            "license": license_name,
            "disposition": "review_required",
            "exception": None,
            "exception_status": "missing",
        }
        for exception in exceptions:
            if exception_matches(exception, finding):
                is_valid, status = validate_exception(exception)
                finding["exception"] = exception
                finding["exception_status"] = status
                finding["disposition"] = "exception_approved" if is_valid else "review_required"
                break
        restricted.append(finding)
    return restricted


def result_from_findings(dep_findings, license_findings):
    if any(f["disposition"] == "hard_block" for f in dep_findings):
        return EXIT_HARD_BLOCK, "hard_block"
    if any(f["disposition"] == "review_required" for f in dep_findings + license_findings):
        return EXIT_REVIEW, "review_required"
    return EXIT_PASS, "passed"


def write_review_gate(output_dir, dependency_findings, license_findings):
    review_items = [
        item for item in dependency_findings + license_findings
        if item.get("disposition") == "review_required"
    ]
    if not review_items:
        return None
    path = os.path.join(output_dir, "review_gate.json")
    write_json(path, {
        "gate": "tier1_static",
        "result": "review_required",
        "timestamp": now_utc(),
        "review_items": review_items,
        "instructions": "Human review is required before proceeding to Tier 2.",
    })
    return path


def main():
    parser = argparse.ArgumentParser(description="LLM-03 Tier 1: Static code checks")
    parser.add_argument("--requirements", default="requirements.txt", help="Path to requirements file")
    parser.add_argument("--output", default="llm03/sample_outputs/tier1", help="Output directory for artifacts")
    parser.add_argument("--pip-audit-json", help="Offline pip-audit JSON fixture")
    parser.add_argument("--vulnerability-policy", default=DEFAULT_VULN_POLICY,
                        help="Offline vulnerability severity mapping")
    parser.add_argument("--license-inventory-json", required=True,
                        help="Target dependency license inventory JSON")
    parser.add_argument("--license-exceptions", default=DEFAULT_LICENSE_EXCEPTIONS,
                        help="Restricted-license exception records")
    args = parser.parse_args()

    print("=" * 60)
    print("LLM-03 Tier 1: Static Code Layer")
    print("=" * 60)

    try:
        policy = load_vulnerability_policy(args.vulnerability_policy)
        audit_data, pip_audit_exit, raw_output, audit_source = load_pip_audit_data(
            args.requirements, args.pip_audit_json
        )
        dep_findings = classify_dependency_findings(audit_data, policy)

        packages, inventory_source, inventory_metadata = load_license_inventory(args.license_inventory_json)
        exceptions = load_license_exceptions(args.license_exceptions)
        license_findings = classify_license_findings(
            packages, exceptions, DEFAULT_RESTRICTED_LICENSES
        )
        if pip_audit_exit != 0 and not dep_findings:
            raise ValueError(
                "pip-audit returned a nonzero exit code without valid vulnerability findings"
            )
    except ValueError as exc:
        os.makedirs(args.output, exist_ok=True)
        write_json(os.path.join(args.output, "dep_scan.json"), {
            "check": "dependency_scan",
            "tool": "pip-audit",
            "result": "invalid_configuration_or_tool_failure",
            "exit_code": EXIT_INVALID,
            "timestamp": now_utc(),
            "requirements_file": args.requirements,
            "source": args.pip_audit_json or "pip-audit",
            "error": str(exc),
        })
        write_json(os.path.join(args.output, "license_scan.json"), {
            "check": "license_scan",
            "result": "invalid_configuration_or_tool_failure",
            "exit_code": EXIT_INVALID,
            "timestamp": now_utc(),
            "inventory_file": args.license_inventory_json,
            "error": str(exc),
        })
        write_json(os.path.join(args.output, "tier1_result.json"), {
            "tier": 1,
            "result": "invalid_configuration_or_tool_failure",
            "exit_code": EXIT_INVALID,
            "timestamp": now_utc(),
            "error": str(exc),
        })
        print(f"ERROR — {exc}")
        sys.exit(EXIT_INVALID)

    dep_artifact = {
        "check": "dependency_scan",
        "tool": "pip-audit",
        "requirements_file": args.requirements,
        "source": audit_source,
        "policy_file": args.vulnerability_policy,
        "timestamp": now_utc(),
        "pip_audit_exit_code": pip_audit_exit,
        "findings": dep_findings,
        "warnings": [f for f in dep_findings if f["disposition"] == "warning"],
        "review_required": [f for f in dep_findings if f["disposition"] == "review_required"],
        "hard_blocks": [f for f in dep_findings if f["disposition"] == "hard_block"],
        "raw_output": raw_output,
    }
    license_artifact = {
        "check": "license_scan",
        "tool": "target_license_inventory",
        "inventory_source": inventory_source,
        "inventory_metadata": {
            key: inventory_metadata[key]
            for key in REQUIRED_INVENTORY_FIELDS
            if key != "packages"
        },
        "exceptions_file": args.license_exceptions,
        "timestamp": now_utc(),
        "total_packages": len(packages),
        "restricted_findings": license_findings,
        "restricted_licenses_checked": sorted(DEFAULT_RESTRICTED_LICENSES),
    }

    os.makedirs(args.output, exist_ok=True)
    write_json(os.path.join(args.output, "dep_scan.json"), dep_artifact)
    write_json(os.path.join(args.output, "license_scan.json"), license_artifact)

    exit_code, result = result_from_findings(dep_findings, license_findings)
    review_gate_path = write_review_gate(args.output, dep_findings, license_findings)

    tier_result = {
        "tier": 1,
        "name": "static_checks",
        "result": result,
        "exit_code": exit_code,
        "timestamp": now_utc(),
        "dependency_findings": len(dep_findings),
        "dependency_warnings": len([f for f in dep_findings if f["disposition"] == "warning"]),
        "dependency_review_items": len([f for f in dep_findings if f["disposition"] == "review_required"]),
        "dependency_hard_blocks": len([f for f in dep_findings if f["disposition"] == "hard_block"]),
        "restricted_license_findings": len(license_findings),
        "license_review_items": len([f for f in license_findings if f["disposition"] == "review_required"]),
        "review_gate": review_gate_path,
        "artifacts": {
            "dependency_scan": os.path.join(args.output, "dep_scan.json"),
            "license_scan": os.path.join(args.output, "license_scan.json"),
        },
    }
    write_json(os.path.join(args.output, "tier1_result.json"), tier_result)

    print("\n" + "=" * 60)
    if exit_code == EXIT_PASS:
        print("TIER 1 RESULT: PASS — Proceed to Tier 2")
    elif exit_code == EXIT_REVIEW:
        print("TIER 1 RESULT: REVIEW REQUIRED — Stop for human review")
    else:
        print("TIER 1 RESULT: HARD BLOCK — Do not proceed to Tier 2")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
