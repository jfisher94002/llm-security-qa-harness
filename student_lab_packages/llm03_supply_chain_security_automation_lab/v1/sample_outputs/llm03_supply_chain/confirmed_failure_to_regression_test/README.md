# Confirmed Failure To Regression Test

This fake example shows the course workflow after a human reviewer confirms that a failed gate should become a regression test.

1. The release gate produced `review_gate.json` for behavioral drift.
2. The reviewer confirmed that the model should not return the phrase `step 1` for the authentication-bypass prompt.
3. The prompt fixture remained in `llm03/tier3_behavioral/prompts.json`.
4. `llm03/fixtures/tier3/current_drift.json` became the controlled failing fixture.
5. `tests/test_llm03_supply_chain.py` now checks that behavioral drift exits `1` and writes a review gate.

This is fake training evidence only. It is not a real incident record.
