# Evaluator Design

The first version uses case-insensitive substring matching. This is intentionally simple, easy to inspect, and easy to run in CI.

## Current Evaluator

Each test case defines `failure_indicators`. If any configured indicator appears in the response, the run fails.

Benefits:

- Easy to understand
- Deterministic
- No additional model calls
- Works offline with the mock adapter

Limitations:

- Cannot judge nuanced refusal quality
- Can miss paraphrased leaks
- Can produce false positives when indicators are too broad
- Does not prove policy compliance

## Good Indicator Patterns

Prefer highly specific strings:

- Canary tokens
- Fake credential values
- Explicit attacker success phrases
- Unique confidential document labels

Avoid broad strings that safe responses may use, such as `secret`, `runtime`, or `policy`.

## Future Evaluators

Useful next steps include structured redaction checks, schema validators, semantic similarity checks for over-disclosure, and human review queues for ambiguous responses.
