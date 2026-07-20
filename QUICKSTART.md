# Quickstart

This quickstart runs the harness locally with the default mock adapter.

## 1. Check Python

Python 3.10 or newer is required.

```bash
python3 --version
```

## 2. Install Requirements

The default LLM01/LLM02 harness uses only the Python standard library. LLM03 signature verification uses the maintained `cryptography` package.

```bash
python3 -m pip install -r requirements.txt
```

## 3. Run The Starter Cases

```bash
python3 runner/run_tests.py
```

Expected outputs:

```text
sample_outputs/run_log.csv
sample_outputs/failures.json
sample_outputs/summary.md
```

## 4. Repeat Each Case

Repeated runs help expose nondeterministic failures when you connect a real model.

```bash
python3 runner/run_tests.py --runs 5
```

## 5. Run A Focused Subset

Run all LLM02 disclosure cases:

```bash
python3 runner/run_tests.py --owasp LLM02
```

Run only canary-tagged cases:

```bash
python3 runner/run_tests.py --tag canary
```

Combine filters with repeated runs:

```bash
python3 runner/run_tests.py --owasp LLM02 --tag canary --runs 5
```

Filter matching is case-insensitive, but reports keep the original case values from the JSON files.

## 6. Try A Real Adapter

Ollama example:

```bash
cp config/ollama.example.yaml config/ollama.local.yaml
python3 runner/run_tests.py --config config/ollama.local.yaml
```

OpenAI example:

```bash
cp config/openai.example.yaml config/openai.local.yaml
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
python3 runner/run_tests.py --config config/openai.local.yaml
```

Never commit real API keys, tokens, private prompts, customer records, or production retrieval documents.

## 7. Read Results Carefully

A pass means the response did not contain the configured failure indicators. It does not prove the system is secure, robust, compliant, or safe against variants of the same attack.

## 8. CI Checks

Pull requests and pushes to `main` run GitHub Actions validation for JSON syntax, Python syntax, the default mock run, a repeated mock run with `--runs 2`, a filtered mock run, and the offline LLM03 unittest suite.

## 9. Try The LLM03 Supply Chain Lab

Run the offline pre-merge gate:

```bash
python3 llm03/run_llm03.py --gate pre-merge \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --output ./tmp_results/llm03-pre-merge
```

Run the offline pre-deployment gate across all three tiers:

```bash
python3 llm03/run_llm03.py --gate pre-deploy \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json \
    --model fixture-model \
    --baseline llm03/fixtures/tier3/baseline_pass.json \
    --current-responses-json llm03/fixtures/tier3/current_pass.json \
    --output ./tmp_results/llm03-pre-deploy
```

Use `docs/llm03_results_interpretation.md` to read `gate_result.json`, `review_gate.json`, and the tier evidence.
