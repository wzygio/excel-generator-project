# Observability

This file is the project-level entrypoint for signals Codex can use to verify work, diagnose failures, and keep development stable.

## Runtime Signals

- Task runs should write `trace.jsonl`, `run_summary.json`, `memory_candidates.json`, and outputs under `specs/runs/<run_id>/`.
- Skill results should expose artifacts, warnings, errors, and memory candidates through the Agent Runtime contracts.
- Runtime output should follow the enterprise output architecture in `D:\wzy\Visionox-Docs_Backup\dev-docs\dev-system_arch\runtime-output-architecture.md`.
- Generated Harness audits and cleanup notes live under `references/generated/`.

## Output Observation Map

Use `output/` artifacts as Agent Observation inputs only after choosing the smallest useful signal. Prefer compact summaries over raw logs, screenshots, or workbooks.

| Observation Need | Preferred Paths | How To Use |
|---|---|---|
| Run result status | `output/observations/runs/`, `specs/runs/<run_id>/run_summary.json` | Read first to determine pass/fail, produced artifacts, warnings, and next diagnostic path. |
| Skill contract result | `output/observations/skills/`, `specs/runs/<run_id>/trace.jsonl` | Confirm Skill inputs, outputs, artifact refs, and structured errors before changing code. |
| Cross-artifact summary | `output/observations/summaries/` | Use when multiple logs/artifacts exist; this is the preferred context for Agent Verify. |
| Smoke result | `output/observations/smoke/`, `output/smoke/unit/`, `output/smoke/integration/`, `output/smoke/e2e/`, `output/smoke/business/` | Read smoke summary first; inspect payload/stdout/stderr only if the summary is insufficient. |
| Quality gate result | `output/audits/quality/`, `references/generated/harness-check.json` | Use pytest/ruff/pyright/harness summaries to decide whether Verify passed. |
| Runtime/tool audit | `output/audits/runtime/`, `output/traces/runtime/`, `output/traces/tools/` | Use to inspect tool dispatch, allowlist behavior, artifact manifests, and runtime state transitions. |
| Data validation | `output/artifacts/data/validation/` | Use schema, row-count, and business-rule validation reports before opening large workbooks. |
| Generated deliverables | `output/artifacts/reports/generated/`, `output/artifacts/reports/upload_ready/`, `output/artifacts/exports/user_downloads/` | Verify file existence, size, workbook sheet summaries, and user-download copies. |
| Source/input replay | `output/artifacts/reports/source/`, `output/downloads/raw/finereport/`, `output/downloads/raw/browser/`, `output/downloads/raw/api/` | Use only when reproducing input acquisition or source data issues. |
| Excel/decryption diagnosis | `output/artifacts/workbooks/decrypted/`, `output/artifacts/workbooks/normalized/`, `output/diagnostics/excel/` | Use when workbook parsing, COM, lock, or encrypted-file behavior fails. |
| RPA/browser failure | `output/diagnostics/rpa/`, `output/diagnostics/browser/`, `output/traces/browser/`, `output/logs/rpa/` | Inspect screenshots/HTML/trace after reading smoke/run summaries. |
| Network/external failure | `output/diagnostics/network/`, `output/logs/external/`, `output/downloads/failed/` | Inspect only sanitized summaries or redacted responses; never expose secrets or session material. |
| General logs | `output/logs/application/`, `output/logs/agent/`, `output/logs/runtime/`, `output/logs/skills/`, `output/logs/infrastructure/` | Use after compact observations fail to explain the issue. Prefer targeted log slices. |
| Failure bundle | `output/diagnostics/failures/` | Use as the final escalation bundle when individual observations are insufficient. |

## Verification Entrypoints

- Documentation / Harness only: inspect the diff and verify referenced paths exist.
- Agent / Skill / Spec changes: run `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short`.
- Broader Python behavior: run `uv run pytest tests/ -v --tb=short` when shared contracts or risky flows changed.
- Type and lint-sensitive changes: run `uv run pyright` and `uv run ruff check .`.
- CopilotKit UI changes: run `npm run typecheck`, `npm run build`, and a real browser/UI smoke in addition to backend tests.

## Diagnostics

- Start from the failing run directory when a TaskSpec fails.
- Start from `output/observations/` when a Runtime artifact exists; only then inspect traces, diagnostics, or logs.
- Inspect `trace.jsonl` before changing code.
- Check `run_summary.json` for status, artifacts, and memory candidate paths.
- Do not write secrets, credentials, cookies, tokens, or portal sessions into trace, logs, memory, or docs.

## Update Rules

- Update this file when trace locations, log locations, smoke checks, or validation commands change.
- Keep detailed implementation notes in the relevant design or agent contract document; keep this file as an entrypoint.
