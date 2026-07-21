# Confirmed Failure To Regression Test Example

This fake example shows how a review finding becomes a regression test.

1. A release gate found behavioral drift for `safety_refusal`.
2. A reviewer confirmed the drift matters.
3. The prompt threshold and expected evidence were kept as an offline regression fixture.
4. The unit test now proves the changed response exits `1` instead of passing.

No real model output, customer data, credentials, or internal prompts are included.
