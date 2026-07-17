# Task Plan: Task3 daily-report wrapper interface audit

## Goal

Verify and, if necessary, repair the external project wrapper and Streamlit UI so they invoke the current installed `daily-report-generator` as a decoupled public CLI and let users download the generated Mod0–Mod1 workbook.

## Source and authorization

- Issue: `D:/wzy/Python/excel-generator-project/.scratch/daily-report-wrapper-task3-interface-audit/issues/01-wrapper-interface-and-ui-smoke.md`
- Requirement: Task3 in `C:/Users/V0141351/.agents/skills/daily-report-generator/docs/dev_docs/refactor-skill.md`
- The maintainer explicitly instructed direct end-to-end execution on 2026-07-17; this records approval of this plan, interface boundary, and verification priority.

## Current Phase

Phase 4 – completed

## Phases

### Phase 1: Contract and configuration audit

- [x] Verify the wrapper uses only public generator root/CLI/output configuration and does not encode Mod business rules.
- [x] Verify current configured root resolves the installed generator CLI and that the default invocation omits `--workspace`.
- [x] Record actual generator workflow/defaults and UI download handoff in findings.
- **Status:** completed

### Phase 2: Focused regression and boundary repair

- [x] Add RED/GREEN coverage that the public CLI runs under the configured generator interpreter rather than the wrapper virtual environment.
- [x] Repair the proven runtime coupling: choose the typed, configured generator interpreter for CLI execution while preserving the fallback to the wrapper interpreter when not configured.
- [x] Confirm current Mod0–Mod1 workflow result mapping, public CLI command construction, and downloadable Excel artifact handling.
- [x] Confirm Mod2–Mod4 remain disabled and no report business rules are copied into the project.
- **Status:** completed

### Phase 3: Browser smoke and download verification

- [x] Read and use `agent-browser`; start the supported Streamlit UI and inspect the default viewport.
- [x] Generate the current-day report through the visible UI, allowing the public generator to run Mod0–Mod1 only.
- [x] Verify success state, workflow, generated Excel artifact, download control, and downloaded file existence without altering source workbooks.
- [x] Record browser observations and any repair/retry evidence in planning files.
- **Status:** completed

### Phase 4: Regression, documentation, and project record

- [x] Run focused wrapper/UI tests and applicable lint/type checks.
- [x] Update architecture/design references for the configured generator interpreter boundary.
- [x] Record the durable interpreter-boundary decision in `docs/ADR/0001-daily-report-generator-interpreter-boundary.md`.
- [x] Review the final diff and hand off artifact path, workflow, and residual warnings.
- **Status:** completed

## Acceptance mapping

| Acceptance criterion | Phase and evidence |
|---|---|
| Installed generator discovery without business coupling | Phase 1 resolver/config inspection and command test |
| Default CLI invocation and explicit forwarding behavior | Phase 1/2 command assertions |
| Excel artifact and `mod0 -> mod1` workflow mapping | Phase 2 tests and Phase 3 live result |
| Streamlit generate/download success | Phase 3 `agent-browser` smoke and downloaded-file check |
| Mod2–Mod4 remain disabled and sources remain unchanged | Phase 2 config inspection and Phase 3 result |
| Regression and traceable handoff | Phase 4 tests, plan evidence, and ADR decision |

## Decisions

| Decision | Rationale |
|---|---|
| Treat the project skill as a public-CLI facade only | The generator owns Mod0–Mod4 business rules and resources; the project owns agent/UI integration. |
| Omit `--workspace` by default | Lets the installed generator use its own root/configuration and avoids coupling to the calling project. |
| UI smoke uses current-day defaults | The user requested a real Mod0–Mod1 daily report generation and download, not a mocked UI flow. |
| Configure the generator interpreter at the facade boundary | The wrapper virtual environment lacked the generator's enterprise Excel dependency; the public skill retains ownership of that runtime and dependency. |

## Errors encountered

| Error | Attempt | Resolution |
|---|---:|---|
| None in this plan yet | — | — |
| PowerShell consumed the browser `@e17` reference | 1 | Use the semantic button locator rather than an unquoted ref. |
| UI real run failed with `ModuleNotFoundError: fr_file_decryption` | 1 | The facade used its own virtual-environment interpreter; add a configured generator interpreter and test it before retrying the UI smoke. |
| `agent-browser download` canceled for Streamlit's blob-backed control | 1 | Use the visible control's normal click; it downloaded the workbook to `C:/Users/V0141351/Downloads/`. |
