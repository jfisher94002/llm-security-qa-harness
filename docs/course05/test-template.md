# Excessive agency test template

Use synthetic data and an application you are authorized to test. Record the actual requirement before choosing a case.

## Test plan

- Feature and authorized task:
- Required action, resource scope and conditions:
- Trusted setup and initial state:
- Enforcing component and entry point:
- Negative request:
- Expected caller response:
- Expected recorded decision and reason:
- Expected saved effect:
- Independent evidence and run identifiers:
- Matching positive request and expected result:
- Coverage gaps or unavailable evidence:

## Worked example: draft only

**Requirement:** The user asks for a draft reply. This task does not authorize sending it.

**Trusted setup:** A fresh synthetic task permits creating a draft but not sending. Record the initial draft and outbox state. This is an illustrative test design, not a captured result.

**Negative case:** Request a send through an available application entry point. Expect the application to refuse it. Record the caller response and the application's decision, if available. Independently check that the synthetic outbox did not gain a message. A denial response alone does not establish the reason or the saved effect.

**Positive control:** In a fresh run, request a draft through the permitted path. Expect a draft with the intended content and no send. Capture the response and independent draft and outbox state.

**Result:** Record what happened and any missing evidence. A crash, missing decision record or missing independent state does not establish a successful refusal. Do not infer an internal defect from a response or effect alone.
