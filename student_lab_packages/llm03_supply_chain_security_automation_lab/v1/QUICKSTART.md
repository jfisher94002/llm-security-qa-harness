# LLM03 Lab Quickstart

Python 3.10 or newer is required.

## 1. Install Dependencies

```bash
python3 -m pip install -r requirements.txt
```

This installs `cryptography`, which Tier 2 uses for maintained Ed25519 verification.

## 2. Run The Pre-Merge Gate

```bash
python3 llm03/run_llm03.py --gate pre-merge \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --output ./tmp_results/pre-merge
```

## 3. Run The Full Offline Pre-Deployment Gate

```bash
python3 llm03/run_llm03.py --gate pre-deploy \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json \
    --model fixture-model \
    --baseline llm03/fixtures/tier3/baseline_pass.json \
    --current-responses-json llm03/fixtures/tier3/current_pass.json \
    --output ./tmp_results/pre-deploy
```

## 4. Run The Controlled Drift Example

```bash
python3 llm03/run_llm03.py --gate release \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json \
    --model fixture-model \
    --baseline llm03/fixtures/tier3/baseline_pass.json \
    --current-responses-json llm03/fixtures/tier3/current_drift.json \
    --output ./tmp_results/release-drift
```

This should exit `1` and write `review_gate.json`.

## 5. Run Tests

```bash
python3 -m unittest discover -s tests -v
```

Read `docs/llm03_results_interpretation.md` before treating a pass as release evidence. Passing checks do not prove the system is secure.
