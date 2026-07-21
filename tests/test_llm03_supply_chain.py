import importlib.util
import builtins
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_cmd(args):
    return subprocess.run(
        [PYTHON, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def load_module(relative_path, name):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Llm03Tier1Tests(unittest.TestCase):
    def test_noncritical_cve_is_warning_and_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_noncritical.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            dep_scan = load_json(Path(tmp) / "dep_scan.json")
            self.assertEqual(dep_scan["warnings"][0]["mapped_severity"], "medium")

    def test_unknown_cve_severity_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_unknown.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertTrue((Path(tmp) / "review_gate.json").exists())

    def test_critical_cve_is_hard_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_critical.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_valid_license_exception_clears_review_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_restricted_approved.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            license_scan = load_json(Path(tmp) / "license_scan.json")
            self.assertEqual(
                license_scan["restricted_findings"][0]["disposition"],
                "exception_approved",
            )

    def test_expired_license_exception_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_restricted_approved.json",
                "--license-exceptions", "llm03/fixtures/tier1/license_exceptions_expired.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_missing_pip_audit_returns_error_artifacts(self):
        module = load_module("llm03/tier1_static/run_tier1.py", "tier1_missing_pip_audit")
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_tier1.py",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ]
            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(module.subprocess, "run", side_effect=FileNotFoundError):
                    with self.assertRaises(SystemExit) as cm:
                        module.main()
            self.assertEqual(cm.exception.code, 3)
            self.assertEqual(load_json(Path(tmp) / "dep_scan.json")["exit_code"], 3)
            self.assertEqual(load_json(Path(tmp) / "license_scan.json")["exit_code"], 3)

    def test_pip_audit_launch_failure_returns_error(self):
        module = load_module("llm03/tier1_static/run_tier1.py", "tier1_launch_failure")
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_tier1.py",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ]
            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(module.subprocess, "run", side_effect=OSError("boom")):
                    with self.assertRaises(SystemExit) as cm:
                        module.main()
            self.assertEqual(cm.exception.code, 3)

    def test_pip_audit_timeout_returns_error(self):
        module = load_module("llm03/tier1_static/run_tier1.py", "tier1_timeout")
        timeout = subprocess.TimeoutExpired(["pip-audit"], 120)
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_tier1.py",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ]
            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(module.subprocess, "run", side_effect=timeout):
                    with self.assertRaises(SystemExit) as cm:
                        module.main()
            self.assertEqual(cm.exception.code, 3)

    def test_pip_audit_nonzero_without_findings_returns_error(self):
        module = load_module("llm03/tier1_static/run_tier1.py", "tier1_nonzero_no_findings")
        completed = subprocess.CompletedProcess(
            ["pip-audit"],
            2,
            stdout='{"dependencies": []}',
            stderr="tool failed",
        )
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_tier1.py",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ]
            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    with self.assertRaises(SystemExit) as cm:
                        module.main()
            self.assertEqual(cm.exception.code, 3)

    def test_malformed_license_inventory_package_entry_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "bad_inventory.json"
            write_json(inventory, {
                "source": "fake",
                "generated_at": "2026-01-15T00:00:00+00:00",
                "requirements_file": "requirements.txt",
                "requirements_sha256": "0" * 64,
                "generator": "test",
                "python_version": "3.10.0",
                "packages": ["not-an-object"],
            })
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", str(inventory),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_missing_inventory_metadata_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "bad_inventory.json"
            write_json(inventory, {"packages": []})
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", str(inventory),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_exception_expiration_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            exceptions = Path(tmp) / "bad_exceptions.json"
            write_json(exceptions, {
                "exceptions": [{
                    "package": "gpl-helper-demo",
                    "version": "0.3.0",
                    "license": "GPL-3.0-only",
                    "approver": "QA",
                    "reason": "bad date",
                    "ticket": "T-1",
                    "expiration": "not-a-date",
                }]
            })
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_restricted_approved.json",
                "--license-exceptions", str(exceptions),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_missing_license_approval_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            exceptions = Path(tmp) / "missing_approval.json"
            write_json(exceptions, {
                "exceptions": [{
                    "package": "gpl-helper-demo",
                    "version": "0.3.0",
                    "license": "GPL-3.0-only",
                }]
            })
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_restricted_approved.json",
                "--license-exceptions", str(exceptions),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_malformed_vulnerability_policy_root_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "bad_policy.json"
            write_json(policy, [])
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--vulnerability-policy", str(policy),
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_vulnerability_policy_entry_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "bad_policy.json"
            write_json(policy, {
                "hard_block_severities": ["critical"],
                "vulnerabilities": {"CVE-2099-0001": {"severity": 12}},
            })
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--vulnerability-policy", str(policy),
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_vulnerability_policy_severity_list_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "bad_policy.json"
            write_json(policy, {
                "hard_block_severities": ["catastrophic"],
                "vulnerabilities": {},
            })
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--vulnerability-policy", str(policy),
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_pip_audit_dependency_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "bad_audit.json"
            write_json(audit, {"dependencies": ["bad"]})
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", str(audit),
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_pip_audit_vulnerability_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "bad_audit.json"
            write_json(audit, {
                "dependencies": [{
                    "name": "demo",
                    "version": "1.0",
                    "vulns": [{"id": 123}],
                }]
            })
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", str(audit),
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_license_exception_root_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            exceptions = Path(tmp) / "bad_exceptions.json"
            write_json(exceptions, {"not_exceptions": []})
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--license-exceptions", str(exceptions),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_license_exception_entry_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            exceptions = Path(tmp) / "bad_exceptions.json"
            write_json(exceptions, {"exceptions": ["bad"]})
            result = run_cmd([
                "llm03/tier1_static/run_tier1.py",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--license-exceptions", str(exceptions),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_license_inventory_generator_uses_target_python(self):
        module = load_module(
            "llm03/tier1_static/generate_license_inventory.py",
            "license_inventory_generator_under_test",
        )
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            stdout = json.dumps([
                {"Name": "target-only-package", "Version": "1.0.0", "License": "MIT"}
            ])
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            requirements = Path(tmp) / "requirements.txt"
            requirements.write_text("target-only-package==1.0.0\n", encoding="utf-8")
            output = Path(tmp) / "inventory.json"
            argv = [
                "generate_license_inventory.py",
                "--requirements", str(requirements),
                "--target-python", sys.executable,
                "--output", str(output),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(module.subprocess, "run", fake_run):
                with self.assertRaises(SystemExit) as cm:
                    module.main()
            self.assertEqual(cm.exception.code, 0)
            self.assertIn("--python", calls[0])
            self.assertIn(sys.executable, calls[0])
            inventory = load_json(output)
            self.assertEqual(inventory["target_python"], Path(sys.executable).name)
            self.assertEqual(inventory["packages"][0]["Name"], "target-only-package")


class Llm03Tier2Tests(unittest.TestCase):
    def test_hash_and_signature_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.fixture.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            artifact = load_json(Path(tmp) / "hash_check.json")
            self.assertTrue(artifact["hash_match"])
            self.assertTrue(artifact["signature"]["verified"])

    def test_hash_mismatch_is_hard_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.hash_mismatch.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_signature_failure_is_hard_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.fixture.json",
                "--signature-file", "llm03/fixtures/tier2/bad_artifact.sig",
                "--public-key-file", "llm03/fixtures/tier2/approved_artifact.pub",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_missing_cryptography_dependency_returns_error(self):
        module = load_module("llm03/tier2_identity/run_tier2.py", "tier2_missing_crypto")

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.startswith("cryptography"):
                raise ImportError("missing for test")
            return real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.fixture.json",
                "--output", tmp,
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(builtins, "__import__", fake_import):
                with self.assertRaises(SystemExit) as cm:
                    module.main()
            self.assertEqual(cm.exception.code, 3)
            artifact = load_json(Path(tmp) / "hash_check.json")
            self.assertIn("cryptography is required", artifact["signature"]["error"])

    def test_malformed_public_key_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            public_key = Path(tmp) / "bad.pub"
            public_key.write_text("abcd", encoding="utf-8")
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.fixture.json",
                "--signature-file", "llm03/fixtures/tier2/approved_artifact.sig",
                "--public-key-file", str(public_key),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_signature_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            signature = Path(tmp) / "bad.sig"
            signature.write_text("not-hex", encoding="utf-8")
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.fixture.json",
                "--signature-file", str(signature),
                "--public-key-file", "llm03/fixtures/tier2/approved_artifact.pub",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_manifest_root_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "bad_manifest.json"
            write_json(manifest, [])
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", str(manifest),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_manifest_models_array_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "bad_manifest.json"
            write_json(manifest, {"models": "bad"})
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", str(manifest),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_manifest_entry_hash_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "bad_manifest.json"
            write_json(manifest, {"models": [{"file_name": "approved_artifact.txt", "sha256": "bad"}]})
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", str(manifest),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_manifest_signature_path_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "bad_manifest.json"
            write_json(manifest, {
                "models": [{
                    "file_name": "approved_artifact.txt",
                    "sha256": "0" * 64,
                    "signature_file": str(Path("bad.sig").resolve()),
                }]
            })
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", str(manifest),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_malformed_manifest_public_key_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "bad_manifest.json"
            write_json(manifest, {
                "models": [{
                    "file_name": "approved_artifact.txt",
                    "sha256": "0" * 64,
                    "ed25519_public_key": "abcd",
                }]
            })
            result = run_cmd([
                "llm03/tier2_identity/run_tier2.py",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", str(manifest),
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)


class Llm03Tier3Tests(unittest.TestCase):
    def write_prompt_file(self, directory, prompts):
        path = Path(directory) / "prompts.json"
        write_json(path, {"prompts": prompts})
        return path

    def load_default_prompts(self):
        return load_json(REPO_ROOT / "llm03" / "tier3_behavioral" / "prompts.json")["prompts"]

    def test_matching_fixture_responses_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/tier3_behavioral/compare_responses.py",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current", "llm03/fixtures/tier3/current_pass.json",
                "--prompts", "llm03/tier3_behavioral/prompts.json",
                "--output", str(Path(tmp) / "results.json"),
            ])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            artifact = load_json(Path(tmp) / "results.json")
            self.assertEqual(artifact["checks_run"], 3)
            self.assertIn("baseline_similarity_score", artifact["results"][0])

    def test_missing_baseline_prompt_exits_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = load_json(REPO_ROOT / "llm03/fixtures/tier3/baseline_pass.json")
            baseline["results"] = baseline["results"][1:]
            baseline_path = Path(tmp) / "baseline.json"
            write_json(baseline_path, baseline)
            result = run_cmd([
                "llm03/tier3_behavioral/compare_responses.py",
                "--baseline", str(baseline_path),
                "--current", "llm03/fixtures/tier3/current_pass.json",
                "--prompts", "llm03/tier3_behavioral/prompts.json",
                "--output", str(Path(tmp) / "results.json"),
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertTrue((Path(tmp) / "results.json").exists())

    def test_missing_current_prompt_exits_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = load_json(REPO_ROOT / "llm03/fixtures/tier3/current_pass.json")
            current["results"] = current["results"][:-1]
            current_path = Path(tmp) / "current.json"
            write_json(current_path, current)
            result = run_cmd([
                "llm03/tier3_behavioral/compare_responses.py",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current", str(current_path),
                "--prompts", "llm03/tier3_behavioral/prompts.json",
                "--output", str(Path(tmp) / "results.json"),
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_empty_prompt_set_exits_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompts = self.write_prompt_file(tmp, [])
            result = run_cmd([
                "llm03/tier3_behavioral/compare_responses.py",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current", "llm03/fixtures/tier3/current_pass.json",
                "--prompts", str(prompts),
                "--output", str(Path(tmp) / "results.json"),
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_duplicate_prompt_ids_exit_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompts = self.load_default_prompts()
            prompts[1]["id"] = prompts[0]["id"]
            prompt_path = self.write_prompt_file(tmp, prompts)
            result = run_cmd([
                "llm03/tier3_behavioral/compare_responses.py",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current", "llm03/fixtures/tier3/current_pass.json",
                "--prompts", str(prompt_path),
                "--output", str(Path(tmp) / "results.json"),
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_unknown_check_type_exits_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompts = self.load_default_prompts()
            prompts[0]["check_type"] = "semantic_vibes"
            prompt_path = self.write_prompt_file(tmp, prompts)
            result = run_cmd([
                "llm03/tier3_behavioral/compare_responses.py",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current", "llm03/fixtures/tier3/current_pass.json",
                "--prompts", str(prompt_path),
                "--output", str(Path(tmp) / "results.json"),
            ])
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_changed_response_with_required_keywords_triggers_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = load_json(REPO_ROOT / "llm03/fixtures/tier3/current_pass.json")
            current["results"][2]["response"] = (
                "A SHA-256 check returns a hash digest, but this response now adds a long, "
                "different explanation about release ceremonies, unrelated audit notes, "
                "supplier questionnaires, escalation queues, and classroom examples."
            )
            current_path = Path(tmp) / "current.json"
            write_json(current_path, current)
            result = run_cmd([
                "llm03/tier3_behavioral/compare_responses.py",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current", str(current_path),
                "--prompts", "llm03/tier3_behavioral/prompts.json",
                "--output", str(Path(tmp) / "results.json"),
            ])
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            artifact = load_json(Path(tmp) / "results.json")
            factual = [item for item in artifact["results"] if item["id"] == "factual_consistency"][0]
            self.assertEqual(factual["rule_result"], "PASS")
            self.assertEqual(factual["drift_result"], "FAIL")


class Llm03GateTests(unittest.TestCase):
    def load_gate_module(self):
        return load_module("llm03/run_llm03.py", "run_llm03_gate_under_test")

    def gate_argv(self, tmp):
        return [
            "run_llm03.py",
            "--gate", "pre-merge",
            "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
            "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
            "--output", tmp,
        ]

    def write_tier1_result(self, output_dir, exit_code):
        tier_dir = Path(output_dir) / "tier1_TS"
        tier_dir.mkdir(parents=True, exist_ok=True)
        write_json(tier_dir / "tier1_result.json", {
            "tier": 1,
            "result": "passed" if exit_code == 0 else "review_required",
            "exit_code": exit_code,
            "timestamp": "2026-01-15T00:00:00+00:00",
        })

    def test_premerge_runs_tier1_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/run_llm03.py",
                "--gate", "pre-merge",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_noncritical.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            gate_result = load_json(Path(tmp) / "gate_result.json")
            self.assertEqual([tier["name"] for tier in gate_result["tiers"]], ["tier1_static"])

    def test_tier1_hard_block_stops_before_tier2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/run_llm03.py",
                "--gate", "pre-deploy",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_critical.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.fixture.json",
                "--model", "fixture-model",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current-responses-json", "llm03/fixtures/tier3/current_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            gate_result = load_json(Path(tmp) / "gate_result.json")
            self.assertEqual([tier["name"] for tier in gate_result["tiers"]], ["tier1_static"])

    def test_tier2_hard_block_stops_before_tier3(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/run_llm03.py",
                "--gate", "pre-deploy",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.hash_mismatch.json",
                "--model", "fixture-model",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current-responses-json", "llm03/fixtures/tier3/current_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            gate_result = load_json(Path(tmp) / "gate_result.json")
            self.assertEqual(
                [tier["name"] for tier in gate_result["tiers"]],
                ["tier1_static", "tier2_identity"],
            )

    def test_predeploy_runs_all_three_tiers_with_fixture_current_responses(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/run_llm03.py",
                "--gate", "pre-deploy",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.fixture.json",
                "--model", "fixture-model",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current-responses-json", "llm03/fixtures/tier3/current_pass.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            gate_result = load_json(Path(tmp) / "gate_result.json")
            self.assertEqual(
                [tier["name"] for tier in gate_result["tiers"]],
                ["tier1_static", "tier2_identity", "tier3_behavioral"],
            )

    def test_behavioral_drift_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "llm03/run_llm03.py",
                "--gate", "release",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.fixture.json",
                "--model", "fixture-model",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--current-responses-json", "llm03/fixtures/tier3/current_drift.json",
                "--output", tmp,
            ])
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertTrue((Path(tmp) / "review_gate.json").exists())

    def test_probe_failure_does_not_run_comparison(self):
        module_path = REPO_ROOT / "llm03" / "run_llm03.py"
        spec = importlib.util.spec_from_file_location("run_llm03_under_test", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        calls = []

        def fake_run(cmd, label):
            calls.append(label)
            if "Tier 1" in label:
                tier1_dir = Path(tmp) / "tier1_TS"
                tier1_dir.mkdir(parents=True, exist_ok=True)
                write_json(tier1_dir / "tier1_result.json", {
                    "tier": 1,
                    "result": "passed",
                    "exit_code": 0,
                    "timestamp": "2026-01-15T00:00:00+00:00",
                })
            if "Tier 2" in label:
                tier2_dir = Path(tmp) / "tier2_TS"
                tier2_dir.mkdir(parents=True, exist_ok=True)
                write_json(tier2_dir / "hash_check.json", {
                    "check": "asset_identity",
                    "result": "PASS",
                    "exit_code": 0,
                    "timestamp": "2026-01-15T00:00:00+00:00",
                })
            if "Running behavioral probes" in label:
                return 3
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_llm03.py",
                "--gate", "pre-deploy",
                "--pip-audit-json", "llm03/fixtures/tier1/pip_audit_pass.json",
                "--license-inventory-json", "llm03/fixtures/tier1/license_inventory_pass.json",
                "--model-file", "llm03/fixtures/tier2/approved_artifact.txt",
                "--manifest", "llm03/fixtures/tier2/release_manifest.fixture.json",
                "--model", "fixture-model",
                "--baseline", "llm03/fixtures/tier3/baseline_pass.json",
                "--output", tmp,
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(module, "run", fake_run):
                with mock.patch.object(module, "timestamp", return_value="TS"):
                    with self.assertRaises(SystemExit) as cm:
                        module.main()
        self.assertEqual(cm.exception.code, 3)
        self.assertIn("Tier 3: Running behavioral probes", calls)
        self.assertNotIn("Tier 3: Comparing against baseline", calls)

    def test_child_exit_one_without_artifact_is_invalid_not_review(self):
        module = self.load_gate_module()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "argv", self.gate_argv(tmp)):
                with mock.patch.object(module, "timestamp", return_value="TS"):
                    with mock.patch.object(module, "run", return_value=1):
                        with self.assertRaises(SystemExit) as cm:
                            module.main()
            self.assertEqual(cm.exception.code, 3)
            gate_result = load_json(Path(tmp) / "gate_result.json")
            self.assertEqual(gate_result["result"], "invalid_configuration_or_tool_failure")
            self.assertIn("artifact_errors", gate_result)

    def test_malformed_tier_artifact_is_invalid(self):
        module = self.load_gate_module()

        def fake_run(cmd, label):
            tier_dir = Path(tmp) / "tier1_TS"
            tier_dir.mkdir(parents=True, exist_ok=True)
            (tier_dir / "tier1_result.json").write_text("{bad", encoding="utf-8")
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "argv", self.gate_argv(tmp)):
                with mock.patch.object(module, "timestamp", return_value="TS"):
                    with mock.patch.object(module, "run", fake_run):
                        with self.assertRaises(SystemExit) as cm:
                            module.main()
            self.assertEqual(cm.exception.code, 3)

    def test_process_artifact_exit_code_mismatch_is_invalid(self):
        module = self.load_gate_module()

        def fake_run(cmd, label):
            self.write_tier1_result(tmp, 0)
            return 1

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "argv", self.gate_argv(tmp)):
                with mock.patch.object(module, "timestamp", return_value="TS"):
                    with mock.patch.object(module, "run", fake_run):
                        with self.assertRaises(SystemExit) as cm:
                            module.main()
            self.assertEqual(cm.exception.code, 3)

    def test_unexpected_child_exit_code_is_invalid(self):
        module = self.load_gate_module()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "argv", self.gate_argv(tmp)):
                with mock.patch.object(module, "timestamp", return_value="TS"):
                    with mock.patch.object(module, "run", return_value=9):
                        with self.assertRaises(SystemExit) as cm:
                            module.main()
            self.assertEqual(cm.exception.code, 3)

    def test_sys_executable_is_used_for_child_commands(self):
        module = self.load_gate_module()
        calls = []

        def fake_run(cmd, label):
            calls.append(cmd)
            self.write_tier1_result(tmp, 0)
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "argv", self.gate_argv(tmp)):
                with mock.patch.object(module, "timestamp", return_value="TS"):
                    with mock.patch.object(module, "run", fake_run):
                        with self.assertRaises(SystemExit) as cm:
                            module.main()
            self.assertEqual(cm.exception.code, 0)
            self.assertTrue(calls)
            self.assertTrue(all(cmd[0] == sys.executable for cmd in calls))


class PackageManifestTests(unittest.TestCase):
    def test_package_manifest_covers_zip_payload(self):
        zip_path = (
            REPO_ROOT
            / "student_lab_packages"
            / "llm03_supply_chain_security_automation_lab"
            / "LLM03_Supply_Chain_Security_Automation_Lab_v1.zip"
        )
        if zip_path.exists():
            import zipfile

            with zipfile.ZipFile(zip_path) as archive:
                names = sorted(name for name in archive.namelist() if not name.endswith("/"))
                manifest = json.loads(archive.read("v1/PACKAGE_MANIFEST.json"))
        elif (REPO_ROOT / "PACKAGE_MANIFEST.json").exists():
            names = [
                "v1/" + path.relative_to(REPO_ROOT).as_posix()
                for path in sorted(REPO_ROOT.rglob("*"))
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
                and "tmp_results" not in path.parts
            ]
            manifest = load_json(REPO_ROOT / "PACKAGE_MANIFEST.json")
        else:
            self.skipTest("student package manifest has not been built yet")
        manifest_path = manifest["manifest_path"]
        payload = manifest["payload"]
        self.assertEqual(manifest_path, "v1/PACKAGE_MANIFEST.json")
        payload_paths = {entry["path"] for entry in payload}
        zip_payload = {name for name in names if name != manifest_path}
        self.assertEqual(payload_paths, zip_payload)
        self.assertNotIn(manifest_path, payload_paths)


class BehavioralRunnerBoundaryTests(unittest.TestCase):
    def setUp(self):
        if not (REPO_ROOT / "runner" / "run_tests.py").exists():
            self.skipTest("LLM01/LLM02 runner is not included in the LLM03-only student package")

    def test_default_runner_still_executes_llm01_llm02_cases_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd(["runner/run_tests.py", "--output", tmp])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Selected 20 of 20 case(s)", result.stdout)
            self.assertIn("20 passed", result.stdout)
            self.assertTrue((Path(tmp) / "run_log.csv").exists())
            self.assertTrue((Path(tmp) / "failures.json").exists())
            self.assertTrue((Path(tmp) / "summary.md").exists())

    def test_llm02_filter_still_executes_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd(["runner/run_tests.py", "--owasp", "LLM02", "--output", tmp])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Ran 10 case run(s)", result.stdout)
            self.assertIn("10 passed", result.stdout)
            summary = (Path(tmp) / "summary.md").read_text(encoding="utf-8")
            self.assertIn("LLM02", summary)

    def test_behavioral_runner_excludes_llm03_supply_chain_definitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd([
                "runner/run_tests.py",
                "--cases", "test_cases/llm03_supply_chain",
                "--output", tmp,
            ])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no JSON test cases found", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
