# llm-security-qa-harness

Lightweight local harness for **LLM security regression testing**: you define prompts and string patterns that should **not** appear in model output; the runner records pass/fail per case and writes reports under `sample_outputs/`.

**Scope:** This tool currently uses **simple substring checks** on responses. It is useful for repeatable smoke checks and regression gates, not for proving that a model is safe in general.

## Run

```bash
python3 runner.py
```

No dependencies beyond Python 3 (standard library only). A **placeholder** model stub is used until you wire in a real inference path.

## Test case format (`test_cases.json`)

Each case is a JSON object with:

| Field | Meaning |
| ----- | ------- |
| `id` | Stable identifier |
| `category` | e.g. `prompt_injection`, `sensitive_disclosure` |
| `title` | Short human-readable name |
| `prompt` | Text sent to the model |
| `failure_indicators` | List of substrings; **if any** appears in the response, the case **fails** |
| `expected_safe_behavior` | What a good response should do (documentation for humans; not executed) |
| `severity` | Your own severity label (e.g. `high`) |

## What a passing test means

A case **passes** when **none** of the `failure_indicators` appear anywhere in the model’s response (plain substring match). That only shows the output did not contain those specific strings on this run—it does **not** mean the model is robust to all attacks, free of other harmful content, or compliant with policy.

## Outputs

After a run:

- `sample_outputs/run_log.csv` — one row per case
- `sample_outputs/failures.json` — cases where at least one indicator matched
- `sample_outputs/summary.md` — counts and timestamp
