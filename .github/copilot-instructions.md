# Copilot Review Instructions

This repository is a small Python starter kit for LLM security QA focused on OWASP LLM01 Prompt Injection and LLM02 Sensitive Information Disclosure.

When reviewing changes:

- Prioritize correctness, security regressions, missing validation, and reproducibility over style-only feedback.
- Treat all `test_assets/` and `test_cases/` data as fake test fixtures. Flag additions that look like real credentials, real PII, private prompts, or proprietary customer data.
- For runner changes, check that JSON loading, repeated runs, mock-by-default behavior, and report writing remain simple and deterministic.
- For model adapter changes, flag accidental requirements for API keys or network access in the default path.
- For evaluator changes, call out broad failure indicators that are likely to create false positives and overly narrow indicators that miss obvious leaks.
- For documentation changes, preserve the warning that passing tests does not prove an application is secure.

Useful validation commands:

```bash
python3 -c 'import json, pathlib; files=sorted(pathlib.Path(".").rglob("*.json")); [json.load(p.open(encoding="utf-8")) for p in files]; print(f"validated {len(files)} JSON file(s)")'
python3 -m compileall runner
python3 runner/run_tests.py
git diff --check
```
