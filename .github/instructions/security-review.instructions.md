---
applyTo: "**/*.py,**/*.json,**/*.md,config/*.yaml,.sourcery.yaml"
---

Review through an LLM security QA lens. Look for prompt-injection test coverage gaps, unsafe disclosure examples, real-looking secrets, accidental dependence on real API credentials, nondeterministic default behavior, and report formats that make failures hard to audit.

Prefer actionable comments that identify the exact risk and a small fix. Avoid requesting abstractions unless they reduce real complexity in this compact starter kit.
