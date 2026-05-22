# Security Policy

This repository contains safe examples for LLM security QA practice. It should not contain real secrets, real customer data, private prompts, internal documents, or production retrieval content.

## Do Not Submit Sensitive Data

Please do not include any of the following in issues, pull requests, comments, screenshots, logs, or sample outputs:

- API keys, tokens, passwords, private keys, or session cookies
- customer names, emails, support tickets, or other personal data
- production prompts, system messages, tool schemas, or retrieval documents
- internal endpoints, architecture details, or incident data

Use synthetic examples only. If you need to describe a problem, replace sensitive values with clearly fake placeholders before posting.

## Reporting Sensitive Concerns

If you believe you found a sensitive-data exposure related to this repository, do not post the details publicly. Open a minimal issue that says you have a sensitive concern and ask for a private contact path, or contact the repository owner through GitHub.

Include only enough public detail to route the report. Do not attach secrets, private logs, customer data, or exploit output.

## Scope

This repo is for safe, repeatable testing examples. Passing the included checks does not prove that a model, application, retrieval system, or agent is secure.

Use separate private workflows for testing real systems and scrub artifacts before sharing them.
