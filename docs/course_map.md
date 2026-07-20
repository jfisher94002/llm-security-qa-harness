# Course Map

Use this map to find the parts of the repo that match your course path. You do not need to complete the LLM01 material before using the LLM02 path.

> Passing these tests does **not** prove an application, prompt, model, retrieval system, or agent is secure. It only means the configured failure strings were not observed in the sampled responses for this run.

## Start Here

Run the offline mock harness from the repo root:

```bash
python3 runner/run_tests.py --output ./tmp_results/course-map-start
```

Then open:

- `tmp_results/course-map-start/summary.md`
- `tmp_results/course-map-start/run_log.csv`
- `tmp_results/course-map-start/failures.json`

## LLM01 Prompt Injection Path

Start with:

- `test_cases/llm01_prompt_injection/`
- `test_assets/` for poisoned documents used by indirect tests
- `docs/evaluator_design.md` for how failure indicators are matched
- `sample_outputs/mock_failure_demo/` for fake prompt-injection failures

Useful commands:

```bash
python3 runner/run_tests.py --owasp LLM01 --output ./tmp_results/course-map-llm01
python3 runner/run_tests.py --owasp LLM01 --severity high --output ./tmp_results/course-map-llm01
python3 runner/run_tests.py --owasp LLM01 --tag indirect --runs 3 --output ./tmp_results/course-map-llm01
```

Focus on whether responses follow attacker instructions, role overrides, hidden document instructions, or policy bypass framing.

## LLM02 Sensitive Information Disclosure Path

Start with:

- `test_cases/llm02_sensitive_disclosure/`
- `sample_outputs/mock_failure_demo/` for fake disclosure failures
- `docs/interpreting_results.md` for how to read pass/fail output

Useful commands:

```bash
python3 runner/run_tests.py --owasp LLM02 --output ./tmp_results/course-map-llm02
python3 runner/run_tests.py --owasp LLM02 --tag canary --output ./tmp_results/course-map-llm02
python3 runner/run_tests.py --owasp LLM02 --severity high --runs 3 --output ./tmp_results/course-map-llm02
```

Focus on whether responses reveal fake canaries, fake credentials, PII-like placeholders, tool schemas, internal endpoint details, or hidden runtime context.

## Supply Chain Security Automation Lab

Start with:

- `llm03/` for the three-tier supply chain harness
- `llm03/policies/` for severity mapping and license exceptions
- `llm03/fixtures/` for offline passing and controlled-failing exercises
- `docs/llm03_results_interpretation.md` for reading gate artifacts

Useful commands:

```bash
python3 llm03/run_llm03.py --gate pre-merge \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --output ./tmp_results/course-map-llm03-premerge

python3 llm03/run_llm03.py --gate pre-deploy \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json \
    --model fixture-model \
    --baseline llm03/fixtures/tier3/baseline_pass.json \
    --current-responses-json llm03/fixtures/tier3/current_pass.json \
    --output ./tmp_results/course-map-llm03-predeploy
```

Keep automation simple. Add focused evidence before adding new abstractions.

## LLM03 Supply Chain Path

Start with:

- `llm03/` for the three-tier supply chain harness
- `test_cases/llm03_supply_chain/` for check definitions
- `llm03/release_manifest.json` to register approved model artifacts
- `demos/llm03_supply_chain_demo.md` for a full step-by-step walkthrough

Useful commands:

```bash
# Tier 1 only — dependency and license scan
python3 llm03/tier1_static/run_tier1.py \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json

# Tier 2 only — hash verification
python3 llm03/tier2_identity/run_tier2.py \
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json

# Record a behavioral baseline for Tier 3
python3 llm03/run_llm03.py --record-baseline --model llama3.2:3b

# Full tiered run
python3 llm03/run_llm03.py --gate release \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json \
    --model fixture-model \
    --baseline llm03/fixtures/tier3/baseline_pass.json \
    --current-responses-json llm03/fixtures/tier3/current_pass.json
```

Focus on whether the dependency set is clean, the model artifact matches the approved hash, and the application behavior still matches the release-approved baseline.
