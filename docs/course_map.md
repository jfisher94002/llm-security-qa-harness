# Course Map

Use this map to find the parts of the repo that match your course path. You do not need to complete the LLM01 material before using the LLM02 path.

## Start Here

Run the offline mock harness from the repo root:

```bash
python3 runner/run_tests.py
```

Then open:

- `sample_outputs/summary.md`
- `sample_outputs/run_log.csv`
- `sample_outputs/failures.json`

## LLM01 Prompt Injection Path

Start with:

- `test_cases/llm01_prompt_injection/`
- `test_assets/` for poisoned documents used by indirect tests
- `docs/evaluator_design.md` for how failure indicators are matched

Useful commands:

```bash
python3 runner/run_tests.py --owasp LLM01
python3 runner/run_tests.py --owasp LLM01 --severity high
python3 runner/run_tests.py --owasp LLM01 --tag indirect --runs 3
```

Focus on whether responses follow attacker instructions, role overrides, hidden document instructions, or policy bypass framing.

## LLM02 Sensitive Information Disclosure Path

Start with:

- `test_cases/llm02_sensitive_disclosure/`
- `sample_outputs/mock_failure_demo/` for fake disclosure failures
- `docs/interpreting_results.md` for how to read pass/fail output

Useful commands:

```bash
python3 runner/run_tests.py --owasp LLM02
python3 runner/run_tests.py --owasp LLM02 --tag canary
python3 runner/run_tests.py --owasp LLM02 --severity high --runs 3
```

Focus on whether responses reveal fake canaries, fake credentials, PII-like placeholders, tool schemas, internal endpoint details, or hidden runtime context.

## Bonus Automation Path

Start with:

- `runner/run_tests.py` for loading, filtering, repeated runs, and report writing
- `runner/evaluators.py` for simple `contains_any`, `contains_all`, and `regex` checks
- `.github/workflows/validate.yml` for the CI validation flow

Useful commands:

```bash
python3 runner/run_tests.py --runs 2
python3 runner/run_tests.py --owasp LLM02 --runs 2
```

Keep automation simple. Add focused checks before adding new abstractions.
