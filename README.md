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
- Simple `contains_any`, `contains_all`, and `regex` evaluators
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
sample_outputs/         Example reports from a mock run
test_assets/            Fake source documents used by indirect tests
test_cases/             JSON test cases grouped by OWASP category
```

## Current Coverage

The starter pack includes 20 cases:

| OWASP Area | Case Count | Example Themes |
| --- | ---: | --- |
| LLM01 Prompt Injection | 10 | direct injection, role override, authority abuse, indirect documents, retrieval poisoning, tool-use coercion |
| LLM02 Sensitive Information Disclosure | 10 | runtime context, canaries, fake credentials, PII placeholders, retrieval leakage, tool schema and environment disclosure |

All fixtures are fake. Do not replace them with production prompts, real customer data, or real secrets.

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
| `expected_safe_behavior` | Human-readable expected behavior |

Optional fields:

| Field | Meaning |
| --- | --- |
| `failure_indicators` | Backward-compatible shorthand for `contains_any` |
| `evaluator` | Explicit evaluator config |
| `asset_path` | File under `test_assets/`, written as a repo-relative path |
| `tags` | List of labels for filtering/reporting later |

Each case must provide failure indicators either as top-level `failure_indicators` or as `evaluator.failure_indicators`.

If `asset_path` is present, the runner rejects absolute paths and path traversal, then replaces `{asset_content}` in the prompt with that file's text.

## Evaluator Modes

The simplest case keeps `failure_indicators` at the top level. This behaves as `contains_any`.

```json
{
  "failure_indicators": ["PROMPT_INJECTION_ACCEPTED"]
}
```

For more control, use an `evaluator` object:

```json
{
  "evaluator": {
    "mode": "contains_all",
    "failure_indicators": ["QA_BYPASS_MODE_CONFIRMED", "disclosure checks disabled"]
  }
}
```

Supported modes:

- `contains_any`: fail if any indicator appears, case-insensitively
- `contains_all`: fail only if all indicators appear, case-insensitively
- `regex`: fail if any Python `re` pattern matches, using case-insensitive, multiline, dot-matches-newline flags

Keep indicators specific. Prefer unique fake success markers and canaries over broad words.

## Filtering Cases

Use filters when you want to run a smaller slice of the pack:

- `--owasp LLM01` or `--owasp LLM02`
- `--tag canary`
- `--category sensitive_information_disclosure`
- `--severity high`

Filters combine with AND semantics, so `--owasp LLM02 --tag canary --runs 5` runs only LLM02 cases tagged `canary`, five times each. Matching is case-insensitive for `owasp_id`, `category`, `severity`, and `tags`; reports preserve the original values from the test case JSON.

If filters select zero cases, the runner exits with a clear error instead of writing an empty report.

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

Checked-in examples:

- `sample_outputs/mock_safe_run/` shows a default mock run with no failures
- `sample_outputs/mock_failure_demo/` shows fake prompt-injection and disclosure failures for teaching

## Boundaries

Read `docs/what_this_is_not.md` before treating results as evidence. This is not a full red-team platform, proof of security, compliance scanner, or replacement for human review.

## Contributing And Security

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before adding cases, docs, or runner changes.
- Read [SECURITY.md](SECURITY.md) before reporting sensitive concerns. Do not post real secrets, customer data, or private system details.

## Extending The Kit

Good next additions are:

- Structured evaluators for refusal quality and data minimization
- Application-specific adapters for your real RAG or agent endpoint
- A CI rule that fails on selected high-severity regressions

Keep test cases small, explicit, and reproducible. Prefer fake canaries and fake credentials that are unmistakably test data.

GitHub Actions validates JSON syntax, Python syntax, and default mock harness runs on pull requests and pushes to `main`.

## AI PR Reviewers

This repo includes setup notes and configuration for Copilot, Sourcery, and Gemini Code Assist PR reviewers in `docs/ai_reviewers.md`.
