# Observability

This file is the project-level entrypoint for signals Codex can use to verify work, diagnose failures, and keep development stable.

## Runtime Signals

- Task runs should write `trace.jsonl`, `run_summary.json`, `memory_candidates.json`, and outputs under `specs/runs/<run_id>/`.
- Skill results should expose artifacts, warnings, errors, and memory candidates through the Agent Runtime contracts.
- Generated Harness audits and cleanup notes live under `references/generated/`.

## Verification Entrypoints

- Documentation / Harness only: inspect the diff and verify referenced paths exist.
- Agent / Skill / Spec changes: run `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short`.
- Broader Python behavior: run `uv run pytest tests/ -v --tb=short` when shared contracts or risky flows changed.
- Type and lint-sensitive changes: run `uv run pyright` and `uv run ruff check .`.
- CopilotKit UI changes: run `npm run typecheck`, `npm run build`, and a real browser/UI smoke in addition to backend tests.

## Diagnostics

- Start from the failing run directory when a TaskSpec fails.
- Inspect `trace.jsonl` before changing code.
- Check `run_summary.json` for status, artifacts, and memory candidate paths.
- Do not write secrets, credentials, cookies, tokens, or portal sessions into trace, logs, memory, or docs.

## Update Rules

- Update this file when trace locations, log locations, smoke checks, or validation commands change.
- Keep detailed implementation notes in the relevant design or agent contract document; keep this file as an entrypoint.
