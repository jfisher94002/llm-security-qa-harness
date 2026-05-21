# Reproducibility

LLM QA results can vary across model versions, temperature settings, system prompts, retrieval contents, and tool configuration. This starter kit keeps the first version simple and encourages recording the details that make a run repeatable.

## What To Record

- Git commit SHA
- Test case directory
- Adapter name and model name
- Config file path, without secrets
- Number of repeated runs
- Temperature and other decoding settings
- Retrieval corpus version when testing RAG behavior
- Application prompt or policy version

## Practical Guidance

Use low temperature for regression checks. Run each case multiple times when using nondeterministic models. Keep sample assets under version control when they are fake and safe to share.

Never commit real credentials, API keys, personal data, private system prompts, or proprietary customer documents.
