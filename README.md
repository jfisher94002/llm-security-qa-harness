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

- Tier 1: pip-audit dependency scan and pip-licenses compliance check
- Tier 2: SHA-256 hash verification against a release manifest
- Tier 3: Fixed-prompt behavioral regression with baseline comparison
- Tiered runner that stops at the first failed tier
- Release manifest template for approved model artifact hashes
- Gate modes for pre-merge, pre-deployment, and full release

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

---

## Quick Run — LLM03 Supply Chain

The LLM-03 harness runs three tiers in order and stops when an earlier tier fails. Behavioral tests never run against an unverified artifact.

| Tier | Layer | Checks | Stops on |
|------|-------|--------|----------|
| 1 | Static code | pip-audit, pip-licenses | Critical CVE or restricted license |
| 2 | Asset identity | SHA-256 vs release manifest | Missing or mismatched hash |
| 3 | Behavioral | Fixed prompts, temp 0, fresh sessions | Drift outside defined tolerance |

```bash
# Pre-merge: dependency and license scan only
python3 llm03/run_llm03.py --gate pre-merge --requirements requirements.txt

# Pre-deployment: Tier 1 + Tier 2
python3 llm03/run_llm03.py --gate pre-deploy \
    --requirements requirements.txt \
    --model-file ./your_model.safetensors

# Release gate: full suite
python3 llm03/run_llm03.py --gate release \
    --requirements requirements.txt \
    --model-file ./your_model.safetensors \
    --model llama3.2:3b \
    --baseline llm03/tier3_behavioral/baseline.json

# Record a behavioral baseline
python3 llm03/run_llm03.py --record-baseline --model llama3.2:3b
```

See `demos/llm03_supply_chain_demo.md` for a full step-by-step walkthrough.

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
  tier1_static/                  Dependency and license checks
  tier2_identity/                Hash verification
  tier3_behavioral/              Behavioral regression (prompts, runner, comparator)
  sample_outputs/                LLM03 artifact output directory
```
