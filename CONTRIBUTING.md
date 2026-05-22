# Contributing

Thanks for helping improve this LLM security QA starter kit. Keep contributions practical, readable, and safe to share in a public repository.

## Use Fake Data Only

- Do not add real credentials, API keys, tokens, private prompts, customer records, internal documents, or production retrieval content.
- Use synthetic examples that are clearly fake.
- Prefer fake canary tokens and fake credential-like strings that cannot be mistaken for real secrets.

## Test Case Guidelines

Good test cases are small and explicit. Each case should include:

- a stable `id`
- the correct `owasp_id`
- a clear category and severity
- a focused prompt
- clear `expected_safe_behavior`
- specific failure indicators or an evaluator config
- tags when they help users run focused subsets

Avoid broad indicators such as single common words. Prefer unique markers that make failures easy to explain.

## Before Opening A PR

Run the harness locally with the mock adapter:

```bash
python3 runner/run_tests.py
```

For changes that affect filtering or repeated runs, also run:

```bash
python3 runner/run_tests.py --runs 2
python3 runner/run_tests.py --owasp LLM02 --runs 2
```

For docs-only changes, check that commands are copy/paste runnable from the repo root.

## Keep The Repo Simple

This project is for QA engineers and SDETs learning practical LLM security testing. Favor plain Python, clear Markdown, fake fixtures, and small changes over large abstractions.

Do not add heavy dependencies, LLM-as-judge evaluation, or platform-specific workflows unless there is a clear issue discussing the tradeoff.
