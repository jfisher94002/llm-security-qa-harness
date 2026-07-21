# LLM Security QA Harness

A practical starter kit for repeatable LLM security QA checks focused on:

- **OWASP LLM01: Prompt Injection**
- **OWASP LLM02: Sensitive Information Disclosure**
- **OWASP LLM03: Supply Chain Testing**

> Passing these tests does **not** prove an application, prompt, model, retrieval system, or agent is secure. It only means the configured checks did not detect the defined failure conditions under the tested circumstances.

---

## What Is Included

### LLM01 and LLM02 — Behavioral Test Runner

- Directory-based JSON test cases for LLM01 and LLM02
- Fake but realistic poisoned documents and sensitive-looking test assets
- A mock model adapter that works without API keys or local models
- Deterministic failure demo mode for teaching and artifact walkthroughs
- Optional Ollama and OpenAI HTTP adapter examples
- Simple `contains_any`, `contains_all`, and `regex` evaluators
- Repeated runs per test case
- Reports written to `sample_outputs/run_log.csv`, `sample_outputs/failures.json`, and `sample_outputs/summary.md`

### LLM03 — Three-Tier Supply Chain Harness

- Tier 1: pip-audit dependency scan and target license-inventory compliance check
- Tier 2: SHA-256 hash verification against a release manifest
- Tier 3: Fixed-prompt behavioral regression with baseline comparison
- Tiered runner that stops at the first failed tier
- Offline policies and fixtures for reproducible lab runs
- Release manifest template for approved model artifact hashes
- Gate modes for pre-merge, pre-deployment, and full release
- Maintained `cryptography` Ed25519 verification for optional detached signatures

---

## Quick Run — LLM01 and LLM02

Default safe run:

```bash
python3 runner/run_tests.py
```

Run each case three times:

```bash
python3 runner/run_tests.py --runs 3
```

Generate intentional failures for demos:

```bash
python3 runner/run_tests.py --demo-failure
```

This mode intentionally injects each test case's configured failure indicators and creates failing artifacts for walkthroughs. By default it writes to:

```text
sample_outputs/demo_failure_run
```

Run a focused subset:

```bash
python3 runner/run_tests.py --owasp LLM02
python3 runner/run_tests.py --tag canary
python3 runner/run_tests.py --category sensitive_information_disclosure --severity high
python3 runner/run_tests.py --owasp LLM02 --tag canary --runs 5
```

Write output somewhere else:

```bash
python3 runner/run_tests.py --output ./tmp_results
```

Use an adapter config:

```bash
python3 runner/run_tests.py --config config/ollama.example.yaml
python3 runner/run_tests.py --config config/openai.example.yaml
```

The default mock adapter is intentionally conservative and does not need network access, API keys, Ollama, or third-party packages.

The LLM01/LLM02 behavioral runner intentionally skips `test_cases/llm03_supply_chain/`; use `llm03/run_llm03.py` for the Supply Chain Security Automation Lab.

---

## Quick Run — LLM03 Supply Chain

The LLM-03 harness runs three tiers in order and stops when an earlier tier fails. Behavioral tests never run against an unverified artifact.

| Tier | Layer | Checks | Stops on |
|------|-------|--------|----------|
| 1 | Static code | dependency severity policy, target license inventory | Critical CVE hard block; unknown CVE or unapproved restricted license review |
| 2 | Asset identity | SHA-256 and optional Ed25519 signature | Missing/mismatched hash or signature failure |
| 3 | Behavioral | Fixed prompts, temp 0, fresh sessions, rule checks plus per-prompt baseline similarity thresholds | Drift requiring human review |

```bash
# Pre-merge: dependency and license scan only
python3 llm03/run_llm03.py --gate pre-merge \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json

# Pre-deployment: Tier 1 + Tier 2 + Tier 3
python3 llm03/run_llm03.py --gate pre-deploy \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json \
    --model fixture-model \
    --baseline llm03/fixtures/tier3/baseline_pass.json \
    --current-responses-json llm03/fixtures/tier3/current_pass.json

# Release gate: full suite
python3 llm03/run_llm03.py --gate release \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json ./target_license_inventory.json \
    --model-file ./your_model.safetensors \
    --model llama3.2:3b \
    --baseline llm03/tier3_behavioral/baseline.json

# Record a behavioral baseline
python3 llm03/run_llm03.py --record-baseline --model llama3.2:3b
```

See `demos/llm03_supply_chain_demo.md` for a full step-by-step walkthrough.

Install dependencies before live LLM03 scans, probes, or Tier 2 signature checks:

```bash
python3 -m pip install -r requirements.txt
```

Exit codes are:

- `0` passed, including recorded non-critical CVE warnings
- `1` human review required
- `2` deterministic hard block
- `3` invalid configuration or tool failure

For interpretation guidance and sample evidence, see `docs/llm03_results_interpretation.md` and `sample_outputs/llm03_supply_chain/`.

---

## Repository Layout

```text
config/                          Example adapter configs (LLM01/02)
docs/                            QA workflow and evaluator notes
runner/                          Python harness for LLM01/02
demos/                           Demo walkthrough scripts
sample_outputs/                  Example reports and demo outputs
test_assets/                     Fake source documents for indirect tests
test_cases/
  llm01_prompt_injection/        LLM01 test case JSON files
  llm02_sensitive_disclosure/    LLM02 test case JSON files
  llm03_supply_chain/            LLM03 check definitions
llm03/
  run_llm03.py                   Tiered harness runner
  release_manifest.json          Approved model artifact hashes
  policies/                      Offline severity policy and license exceptions
  fixtures/                      Fake data for reproducible LLM03 lab runs
  tier1_static/                  Dependency and license checks
  tier2_identity/                Hash verification
  tier3_behavioral/              Behavioral regression (prompts, runner, comparator)
  sample_outputs/                LLM03 artifact output directory
student_lab_packages/            Versioned lab package builds
```
