# LLM01 Prompt Injection Demo

Use this walkthrough to show how the harness runs focused OWASP LLM01 prompt-injection checks and how to inspect the output artifacts.

## Purpose

This demo shows a QA-friendly workflow for testing whether a model or application follows attacker instructions that conflict with the intended task. The checked-in mock adapter is safe and deterministic, so the demo works without API keys or network access.

## Commands

Run all LLM01 cases:

```bash
python3 runner/run_tests.py --owasp LLM01 --output sample_outputs
```

Run high-severity LLM01 cases:

```bash
python3 runner/run_tests.py --owasp LLM01 --severity high --output sample_outputs
```

Run indirect prompt-injection cases repeatedly:

```bash
python3 runner/run_tests.py --owasp LLM01 --tag indirect --runs 3 --output sample_outputs
```

## What To Inspect

Open `sample_outputs/summary.md` first. It gives total runs, pass/fail counts, and failures by OWASP category.

Then inspect `sample_outputs/run_log.csv` for:

- `case_id`: which test ran
- `severity`: the assigned teaching severity
- `matched_indicators`: strings that caused a failure
- `rendered_prompt`: the final prompt after any test asset was inserted
- `response`: the model or adapter response

If failures occur, open `sample_outputs/failures.json`. It contains only failed runs with the matched indicators and full prompt/response details.

## What A Failure Looks Like

A prompt-injection failure is usually not just a rude or unhelpful answer. In this harness, it is a response that contains a configured attacker success marker, such as a fake phrase indicating the model accepted a role override, obeyed hidden document instructions, or disabled disclosure checks.

For teaching, compare a safe mock run with `sample_outputs/mock_failure_demo/`. The failure demo uses fake markers only; do not replace them with real secrets or private prompts.

## Reminder

Passing these checks only means the configured failure indicators were not observed in this run. QA judgment is still required, especially when reviewing natural-language responses that are suspicious but do not match an exact indicator.
