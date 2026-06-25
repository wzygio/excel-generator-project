# Harness Optimization Findings

## Initial Context

- Active plan before this task was `2026-06-25-refactor-harness`.
- Root planning files contain older completed daily-report, Letta, and agent-architecture histories; this task uses an isolated planning directory.
- User wants the optimization organized around Step0 Route, Step1 Observation, Step2 Verify, and Step3 Reflect.

## Research Notes

- `AGENTS.md` is already short and route-oriented, but it still says to add feedback/cleanup notes to `references/retrospective.md`; Step3 requires that file to become mechanism-only, so this needs adjustment.
- `git status --short` shows deleted tracked files under `references/plans/active/index.md`, `references/plans/completed/index.md`, and `references/plans/index.md`; these should be recreated/optimized rather than ignored because `AGENTS.md` routes to `references/plans/`.
- Current `output/` top-level folders include `decrypted_files`, `downloads`, `logs`, `rpa_debug`, `rpa_downloads`, and `task2_smoke`; this confirms the user's concern that system-level artifact classes and business/runtime-specific folders are mixed.
- Current `references/test_references/observability.md` mentions `specs/runs/<run_id>/` and `references/generated/`, but does not yet map Observation-worthy `output/` paths into Verify/Observation usage.
- Current `references/retrospective.md` mixes cleanup mechanism with generated status/result content such as last generated date, latest check, and known cleanup items.
- Route optimization decision: keep `Folder Routes` folder-only and place file-level loading under `Read Guidance` or `Local Documents`, so the Harness still satisfies low-maintenance routing while telling agents when/what/which commands to use.
- `references/plans/index.md`, `references/plans/active/index.md`, and `references/plans/completed/index.md` were missing and have been recreated as folder-only planning routers.
- Enterprise output architecture is now documented externally at `D:\wzy\Visionox-Docs_Backup\dev-docs\dev-system_arch\runtime-output-architecture.md`.
- Runtime output coding convention now maps artifact categories to stable `output/` paths and marks legacy top-level folders such as `decrypted_files`, `rpa_debug`, `rpa_downloads`, and `task2_smoke` as deprecated locations.
- Observability now treats `output/observations/` as the preferred Agent Verify input before traces, diagnostics, logs, or large workbooks.
- Output migration should preserve runtime evidence and avoid deleting files. Empty legacy folders can be removed only after their contents are moved and verified empty.
- Current `output/` migration moved the only decrypted workbook from `output/decrypted_files/` to `output/artifacts/workbooks/decrypted/`.
- Current `output/` migration moved `output/logs/all.log` to `output/logs/application/all.log` and `output/logs/core/info.log` to `output/logs/runtime/info.log`.
- Runtime code was updated so future FineReport raw downloads use `output/downloads/raw/finereport/`, decrypted workbooks use `output/artifacts/workbooks/decrypted/`, normalized workbooks use `output/artifacts/workbooks/normalized/`, and RPA diagnostics use `output/diagnostics/rpa/`.
