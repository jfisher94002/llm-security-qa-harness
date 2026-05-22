# YouTube Demo Outline

This outline fits a short 3 to 5 minute walkthrough for GitHub, YouTube, LinkedIn, or a course lesson.

## Opening Hook

"Most LLM security testing demos are either too abstract or require a full red-team platform. This repo shows the smaller QA workflow: run repeatable prompt-injection and disclosure checks, inspect the artifacts, and decide what needs human review."

## Demo Flow

1. Show the repo structure:

```bash
ls
find test_cases -maxdepth 2 -type f | sort | head
```

2. Run the default offline mock harness:

```bash
python3 runner/run_tests.py --output ./tmp_results/youtube_demo
```

3. Run a focused LLM01 prompt-injection slice:

```bash
python3 runner/run_tests.py --owasp LLM01 --severity high --output ./tmp_results/youtube_demo
```

4. Run a focused LLM02 canary slice:

```bash
python3 runner/run_tests.py --owasp LLM02 --tag canary --output ./tmp_results/youtube_demo
```

5. Open the artifacts:

```bash
cat tmp_results/youtube_demo/summary.md
head -n 5 tmp_results/youtube_demo/run_log.csv
cat tmp_results/youtube_demo/failures.json
```

## Artifacts To Explain

- `summary.md`: quick pass/fail counts and OWASP grouping
- `run_log.csv`: one row per case run for spreadsheet review
- `failures.json`: failed runs with prompt, response, and matched indicators
- `sample_outputs/mock_failure_demo/`: fake examples of what failures look like

## Closing CTA

"Clone the repo, run the mock harness, then add one fake test case that matches your application workflow. Do not add real secrets or customer data. The goal is repeatable QA practice, not proof that a system is secure."
