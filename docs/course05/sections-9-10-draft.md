# Sections 9 and 10: working outline

These outlines are for review. They are not recorded narration. The concurrency comparison is a proposed fixture, not a captured result.

## Section 9: Optional technical practice with automation

Planning target: 12–15 minutes, excluding learner practice. This estimate is provisional and needs a timed script and recording.

1. Orient learners to the repository and the Course 5 local fixture. Explain that the scripts use synthetic requests and no model or payment service. Preview the concurrency and delegated-count exercise in the following bonus section, as promised on Slide 51.
2. Run the six draft starter tests. Explain why each starts with fresh state. A test error or missing evidence is not a pass.
3. Walk through the missing-approval case: request, caller response, recorded reason and independently observed ledger. A denial alone is not enough.
4. Examine the matching-approval positive control and revised-proposal case. Explain how they address an always-deny control and stale authorization.
5. Examine the exact-retry test. Confirm the original receipt is returned and the ledger has no second refund. Report only the tested local path.
6. Explain the catalog and cross-tenant checks. Offered functionality, delivery and enforcement are different observations. A read-only access test needs evidence of what was retrieved or delivered, not a refund ledger assertion by default.
7. Provide a downloadable template and a worked example before learners adapt a test to their own requirement. The template should identify the task and trusted setup, request, enforcing boundary, expected decision and effect, independent evidence, negative case and matching positive control. Keep commands copyable and use synthetic data.
8. Review failures and errors, inspect evidence and add appropriate cases to regression. Close by explaining that the next optional section extends this approach to concurrent and delegated work.

## Section 10: Optional technical practice with concurrency and delegation

Planning target: 12–15 minutes, excluding learner practice. This estimate is provisional and depends on the completed exercise and timed script.

1. Define a shared one-action task and two independently approved proposals. State the expected result before running: at most one new effect across the task. The broken and corrected examples below are proposed until implemented and captured.
2. Build a deliberately vulnerable teaching variant that checks the shared limit outside the write transaction and offers a controlled pause after the check and before the write. Arrange a deterministic schedule in which both requests pass the stale check, then resume. The intended failing outcome is two effects. Verify that the approvals, amounts, different proposal identities and other controls permit the count boundary to be isolated.
3. Compare the corrected variant. The current Lab 2 wraps the budget check and ledger write in a BEGIN IMMEDIATE transaction. Pause before the combined transaction, not at an in-transaction barrier that both workers must reach. Capture the ordering, decisions and independent ledger state. The expected result is one effect and refusal of the other request. A lock error, timeout, missing capture or test error is not evidence of a successful refusal.
4. Record evidence that the check and write are atomic relative to the competing transaction. A function call alone is not proof. Use a fresh run and a matching positive control. A coverage gap applies when a window exists but the test cannot reach it. Report the schedule tested, not a claim about every possible interleaving or production system.
5. Extend the exercise to two helpers under a single parent task. The application supplies the trusted task identity and shared count. A helper request cannot assign or reset that authority. The existing L2-08D cases exercise direct-path and task-count controls. The new question is whether separate helpers share the same parent-task limit. This fixture remains to be designed and implemented.
6. Have learners add a concurrency test to the Section 9 starter suite. Provide a worked example and template once the fixture is independently reviewed and its results are reproducible.

## Assessments and recording readiness

Proposed: five quiz questions after each optional section, consistent with the course's established five-per-section practice. Draft and review them against the final lessons before uploading.

Section 9 requires independent review of the Demo C v3 package and all six starter tests, including evidence assertions, before recording. Section 10 requires a fixture design, implementation, independent review, deterministic runs on the instructor's Mac and captured evidence. Both sections need reviewed narration, slides and download instructions. Do not present a proposed outcome as a recorded result.
