# Validation Guidance

Before finishing, run the smallest relevant verification and report what ran.

- Documentation / Harness only: inspect the diff and verify referenced paths exist.
- Core parser, selector, or business-time changes: run focused unit tests, or broader unit tests for wider risk.
- Agent / Skill / Spec changes: run Agent and Skill unit tests.
- FineReport, file loading, or download changes: run related unit tests; add browser/RPA smoke only when the visible or portal flow changed.
- CopilotKit UI changes: backend tests are not enough; run typecheck, build, and a real browser/UI smoke test.
- Config, dependency, or typing-sensitive changes: run pyright and ruff.
- If a verification command cannot run, state the command, the blocker, and the residual risk.

