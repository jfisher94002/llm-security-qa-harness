# LLM Security QA Harness

A practical starter kit for repeatable LLM security QA checks focused on:

- **OWASP LLM01: Prompt Injection**
- **OWASP LLM02: Sensitive Information Disclosure**

The harness loads JSON test cases from a directory, runs each case one or more times against a model adapter, applies basic string-matching evaluators, and writes CSV/JSON/Markdown reports.

> Passing these tests does **not** prove an application, prompt, model, retrieval system, or agent is secure. It only means the configured failure strings were not observed in the sampled responses for this run.

## What Is Included

- Directory-based JSON test cases for LLM01 and LLM02
- Fake but realistic poisoned documents and sensitive-looking test assets
- A mock model adapter that works without API keys or local models
- Deterministic failure demo mode for teaching and artifact walkthroughs
- Optional Ollama and OpenAI HTTP adapter examples
- Simple `contains_any`, `contains_all`, and `regex` evaluators
- Repeated runs per test case
- Reports written to `sample_outputs/run_log.csv`, `sample_outputs/failures.json`, and `sample_outputs/summary.md`

## Quick Run

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

Use this for videos, screenshots, and teaching workflows where you want realistic `failures.json` and report evidence without needing a vulnerable model.

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

## Repository Layout

```text
config/                 Example adapter configs
docs/                   QA workflow and evaluator notes
runner/                 Python harness implementation
demos/                  Demo walkthrough scripts
sample_outputs/         Example reports and demo outputs
test_assets/            Fake source documents used by indirect tests
test_cases/             JSON test cases grouped by OWASP category
```
