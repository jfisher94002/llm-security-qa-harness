# AI PR Reviewers

This repository is prepared for two AI review tools:

- GitHub Copilot code review
- Sourcery

## GitHub Copilot

Repository-side setup completed:

- An active GitHub repository ruleset named `Copilot automatic PR review` automatically requests Copilot code review for pull requests targeting `main`.
- Draft pull requests are included.
- Repo-wide guidance lives in `.github/copilot-instructions.md`.
- Path-specific review guidance lives in `.github/instructions/security-review.instructions.md`.

Copilot custom instructions are read from the pull request base branch, so merge these files to `main` before expecting them to affect reviews into `main`.

## Sourcery

Repository-side setup completed:

- `.sourcery.yaml` configures Python-focused review behavior and ignores generated/sample-output paths.

Required external setup:

1. Install or authorize the Sourcery GitHub app for `jfisher94002/llm-security-qa-harness`.
2. Confirm the repo is linked in Sourcery.
3. Open a new pull request to confirm Sourcery comments automatically.

## Expectations

AI reviewers are useful first-pass checks. They do not replace human review, secret scanning, tests, or security assessment.
