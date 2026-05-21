# What This Is Not

This repository is intentionally small. It is a QA starter kit for learning and repeatable regression checks, not a complete security product.

It is not:

- A full red-team platform
- Proof that a model, prompt, agent, or application is secure
- A compliance scanner
- A replacement for human review
- A substitute for threat modeling, access control, logging, monitoring, or incident response

Passing tests only means the configured indicators were not observed in the sampled outputs for that run. It does not mean related attacks are blocked, sensitive data cannot leak, or the system is safe in production.

QA judgment is still required. Review failures manually, improve test cases over time, and keep the cases tied to realistic application behavior.
