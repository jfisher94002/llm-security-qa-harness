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
- Optional Ollama and OpenAI HTTP adapter examples
- Simple case-insensitive string evaluators
- Repeated runs per test case
- Reports written to `sample_outputs/run_log.csv`, `sample_outputs/failures.json`, and `sample_outputs/summary.md`

## Quick Run

```bash
python3 runner/run_tests.py
```

Run each case three times:

```bash
python3 runner/run_tests.py --runs 3
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
sample_outputs/         Example reports from a mock run
test_assets/            Fake source documents used by indirect tests
test_cases/             JSON test cases grouped by OWASP category
```

## Test Case Format

Each JSON file can contain one case object or a list of case objects.

Required fields:

| Field | Meaning |
| --- | --- |
| `id` | Stable case identifier |
| `owasp_id` | `LLM01` or `LLM02` |
| `category` | Human-readable category slug |
| `title` | Short test name |
| `severity` | Informational severity label |
| `prompt` | Prompt template sent to the model |
| `failure_indicators` | Strings that must not appear in the model response |
| `expected_safe_behavior` | Human-readable expected behavior |

Optional fields:

| Field | Meaning |
| --- | --- |
| `asset_path` | File under `test_assets/`, written as a repo-relative path |
| `tags` | List of labels for filtering/reporting later |

If `asset_path` is present, the runner rejects absolute paths and path traversal, then replaces `{asset_content}` in the prompt with that file's text.

## Model Adapters

The harness supports three simple adapters:

- `mock`: default, offline, no dependencies
- `ollama`: calls a local Ollama `/api/generate` endpoint
- `openai`: calls the OpenAI chat completions HTTP endpoint using an environment variable for the API key

The examples under `config/` are templates. Do not commit real credentials.

## Reports

After a run:

- `run_log.csv` contains one row per case run
- `failures.json` contains failed case details and matched indicators
- `summary.md` contains aggregate counts and a security caveat

## Extending The Kit

Good next additions are:

- Test case filters by OWASP ID, tag, and severity
- Structured evaluators for refusal quality and data minimization
- Application-specific adapters for your real RAG or agent endpoint
- CI integration that fails on high-severity regressions

Keep test cases small, explicit, and reproducible. Prefer fake canaries and fake credentials that are unmistakably test data.

## AI PR Reviewers

This repo includes setup notes and configuration for Copilot, Sourcery, and Gemini Code Assist PR reviewers in `docs/ai_reviewers.md`.
