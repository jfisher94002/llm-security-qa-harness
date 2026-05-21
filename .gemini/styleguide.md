# Gemini Code Assist Review Style Guide

Review this repository as an LLM security QA starter kit.

Focus on:

- Prompt injection and sensitive disclosure regressions.
- Real secrets, real PII, private prompts, or production data accidentally committed as fixtures.
- Whether the mock adapter remains the default and works without network access or API keys.
- Whether JSON test cases are valid, stable, and easy to extend.
- Whether reports clearly identify failed cases and matched indicators.
- Whether documentation keeps the caveat that passing tests does not prove security.

Keep comments concise and actionable. Prefer bug, security, reproducibility, and missing-test findings over cosmetic suggestions.
