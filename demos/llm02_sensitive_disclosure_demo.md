# LLM02 Sensitive Information Disclosure Demo

Use this walkthrough to show how the harness runs focused OWASP LLM02 disclosure checks without assuming students have already completed an LLM01 lesson.

## Purpose

This demo checks whether a model or application reveals sensitive-looking data when asked to disclose runtime context, fake credentials, canary tokens, tool schemas, internal endpoint details, or private reasoning. The fixtures are synthetic and safe for public demos.

## Commands

Run all LLM02 cases:

```bash
python3 runner/run_tests.py --owasp LLM02 --output ./tmp_results/llm02
```

Run canary-tagged cases:

```bash
python3 runner/run_tests.py --owasp LLM02 --tag canary --output ./tmp_results/llm02
```

Run high-severity LLM02 cases repeatedly:

```bash
python3 runner/run_tests.py --owasp LLM02 --severity high --runs 3 --output ./tmp_results/llm02
```

## What To Inspect

Start with `tmp_results/llm02/summary.md` to confirm how many LLM02 runs executed and whether any failed.

Use `tmp_results/llm02/run_log.csv` to inspect:

- `case_id`: which disclosure scenario ran
- `severity`: the assigned teaching severity
- `matched_indicators`: exact strings or patterns that triggered failure
- `prompt_template`: the original test prompt
- `rendered_prompt`: the final prompt, including any fake asset content
- `response`: the model or adapter response

Use `tmp_results/llm02/failures.json` when you need a compact view of failed runs only.

## Exact Leak Signatures Versus Weaker Evidence

The first version of this harness uses deterministic string and regex matching. A strong failure is an exact fake canary, fake credential, synthetic endpoint, or unique disclosure marker appearing in the response.

Weaker evidence may still matter. A response might describe sensitive behavior, imply access to hidden context, or summarize private-looking details without matching an exact configured indicator. Treat those as review findings even when the automated result passes.

## Reminder

These checks do not catch every semantic leak. Passing tests only means the configured indicators were not observed in the sampled outputs. Keep fake data in the repo and use separate, private workflows for real systems.
