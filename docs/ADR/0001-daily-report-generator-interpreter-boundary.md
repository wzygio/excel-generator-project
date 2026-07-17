# ADR 0001: Configure the daily-report generator interpreter at the facade boundary

Status: accepted

Date: 2026-07-17

## Context

The project `daily_report` facade launches the installed public
`daily-report-generator` CLI. A real Streamlit run failed because the facade
used the calling project's virtual-environment interpreter, while the
generator's enterprise Excel dependency (`fr_file_decryption`) is installed in
its supported runtime.

The wrapper must remain a public-CLI adapter and must not copy generator
dependencies or report business configuration into this repository.

## Decision

Add `agent.daily_report.python_executable` to the typed Agent integration
configuration. When configured, the facade validates and uses this executable
as the first CLI command argument. When it is unset, it keeps the compatible
fallback to the wrapper interpreter.

The setting is an integration/runtime choice only. Generator paths, source
workbooks, Mod rules, and dependency details remain owned by the installed
skill.

## Consequences

- Streamlit, Agent Runtime, and direct facade calls can invoke the supported
  generator environment without coupling their own virtual environment to it.
- An invalid configured executable fails before CLI execution with an explicit
  configuration error.
- Deployments must keep this path aligned with the installed generator
  runtime; an unset value remains supported for homogeneous environments.

## Evidence

- Issue: `.scratch/daily-report-wrapper-task3-interface-audit/issues/01-wrapper-interface-and-ui-smoke.md`
- Plan: `.planning/2026-07-17-daily-report-task3-interface-audit/task_plan.md`
- Implementation: `src/yield_report/shared_kernel/config_model.py`,
  `src/yield_report/skills/daily_report/native_pipeline.py`, and
  `config/global.yaml`
- Tests: `tests/unit/skills/test_daily_report_orchestrator_skill.py` and the
  focused wrapper/UI suite (14 passed)
- UI smoke: 2026-07-17 Streamlit run completed `mod0 -> mod1` and exposed a
  downloaded workbook.
