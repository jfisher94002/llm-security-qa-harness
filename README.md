# llm-security-qa-harness

Minimal local harness: loads JSON cases, runs a placeholder model, checks outputs with substring matching, writes results under `sample_outputs/`.

## Run

```bash
python3 runner.py
```

No dependencies beyond Python 3.

## Test case format

Each object in `test_cases.json` has `id`, `prompt`, and `expected` (substring that must appear in the model response). Optional `xfail` (boolean) marks a case where a substring mismatch is expected; the harness treats a mismatch as a pass for that case (and a match as a failure).

## What a passing test means
A passing result does not mean the system is secure.
It only means that known failure patterns in this test suite did not trigger during this run.
New attack patterns must be continuously added.
