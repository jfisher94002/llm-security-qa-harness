# QA Workflow

Use this harness as a lightweight regression loop for LLM security behavior.

## Suggested Process

1. Pick one risk area, such as LLM01 prompt injection or LLM02 sensitive information disclosure.
2. Write small test cases that describe one attack pattern at a time.
3. Use fake but realistic assets that resemble the documents your system processes.
4. Run the mock adapter first to validate case syntax and reporting.
5. Run against a staging model or application adapter.
6. Review every failure manually before changing prompts, retrieval filters, tools, or policies.
7. Re-run the same cases after each mitigation.

## Case Design Tips

- Keep failure indicators specific enough to avoid flagging safe refusals.
- Include canary strings when testing disclosure paths.
- Do not use real customer data, secrets, private prompts, or production documents.
- Track the exact model, adapter, prompt version, retrieval corpus, and run count.

## Security Warning

Passing tests are useful regression signals, not proof of security. Prompt injection and disclosure risks are open-ended, model-dependent, and sensitive to surrounding application behavior.
