# Harness Optimization Plan

## Goal

Optimize the current references-based Harness around four runtime phases: Route, Observation, Verify, and Reflect.

## Requirements

- Ensure `AGENTS.md` routes by top-level reference folders instead of embedding detailed rules.
- Ensure `references` indexes explain when to read each folder, which files to read, and which commands apply.
- Design an enterprise-grade `output/` architecture and write the design document under `D:\wzy\Visionox-Docs_Backup\dev-docs\dev-system_arch`.
- Update runtime-output coding conventions so code writes artifacts to the proper `output/` subpath.
- Update `references/test_references/observability.md` so Observation-worthy `output/` paths can feed the agent verification/observation stage.
- Convert `references/retrospective.md` into a mechanism-only Reflect router and move existing result/status material to `references/generated`.

## Phases

| Phase | Status | Purpose |
|---|---|---|
| 0. Plan and baseline | complete | Inspect current AGENTS, references indexes, output structure, observability, and retrospective files. |
| 1. Route optimization | complete | Optimize `AGENTS.md` and reference indexes for folder routing plus when/read/command guidance. |
| 2. Observation optimization | complete | Design enterprise output architecture and update runtime-output coding conventions. |
| 3. Verify optimization | complete | Update observability to map output observations into verification feedback. |
| 4. Reflect optimization | complete | Make retrospective mechanism-only and archive/generated prior result content. |
| 5. Verification | complete | Run focused checks for references, Harness check, and diff review. |
| 6. Output directory migration | complete | Move existing `output/` artifacts into the enterprise output architecture without deleting runtime evidence. |

## Decisions

| Decision | Rationale |
|---|---|
| Use an isolated `.planning` task directory | The root planning files contain completed historical tasks and should not be overwritten. |
| Keep generated/archival status outside `retrospective.md` | The user explicitly wants Reflect mechanics to stay lightweight and only loaded near completion. |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| PowerShell parsed `Split-Path $_ -Leaf -eq 'index.md'` as a parameter call | Baseline index scan | Will use regex/path matching instead of mixing `Split-Path` and comparison in one expression. |
| Large multi-file patch failed on slightly different index wording | Route optimization | Split edits into smaller patches based on actual file contents. |
| Full `git diff --check` reported trailing whitespace in pre-existing modified `docs/dev_prompt/active/refactor-harness.md` | Verification | Re-ran diff check excluding that unrelated pre-existing file; touched files passed with only LF/CRLF warnings. |

## Verification

| Command | Result |
|---|---|
| `uv run pytest tests/unit/test_harness_references.py -q --tb=short` | 5 passed |
| `uv run python scripts/harness_check.py --write-audit --json` | status ok |
| `git diff --check -- . ':(exclude)docs/dev_prompt/active/refactor-harness.md'` | passed; LF/CRLF warnings only |
| External output architecture readability check | passed |
| `uv run pytest tests/unit/test_analysis_file_resolver.py tests/unit/test_finereport_client.py tests/unit/test_yield_download_service.py -q --tb=short` | 20 passed |
| `uv run ruff check src/yield_report/infrastructure/analysis_file_resolver.py src/yield_report/infrastructure/finereport_client.py src/yield_report/infrastructure/yield_download_service.py tests/unit/test_analysis_file_resolver.py tests/unit/test_finereport_client.py tests/unit/test_yield_download_service.py` | passed |
| Output legacy top-level directory check | passed |
