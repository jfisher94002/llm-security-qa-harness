# llm-security-qa-harness

Minimal local harness: loads JSON cases, runs a placeholder model, checks outputs with substring matching, writes results under `sample_outputs/`.

## Run

```bash
python3 runner.py
```

No dependencies beyond Python 3.

## Test case format

Each object in `test_cases.json` has `id`, `prompt`, and `expected` (substring that must appear in the model response).
