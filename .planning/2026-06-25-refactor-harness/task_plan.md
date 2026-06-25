# Harness Refactor Plan

## Goal
Complete `docs/dev_prompt/active/refactor-harness.md` end to end: refactor the project Harness, make it runnable through routing and feedback loops, implement the `report_download` Letta wrap-skill smoke path, split the Harness Builder skill into create/refactor skills, and apply the final Harness shape to `D:\wzy\Python\vivo-project`.

## Current Phase
Complete

## Requirements
- Use `planning-with-files` before each major step and keep this plan, findings, and progress updated.
- Use TDD for development work: one public behavior test, minimal implementation, then refactor.
- Preserve user work and runtime artifacts; do not delete user resources or generated report files.
- Use CodeGraph first for structural code understanding because `.codegraph/` exists.
- Search current AGENTS/Harness guidance and GitHub examples where the task explicitly asks for research.
- Output external design documents under `D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev` and `D:\wzy\Visionox-Docs_Backup\dev-docs\codex`.

## Final Checklist
- [x] Step1: Understand current `references` Harness architecture and write a complete Harness architecture diagram to `D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev`.
- [x] Step2: Re-scan and complete Harness module `index.md` files so they list folder paths, not individual files.
- [x] Step2: Refactor `ARCHITECTURE.md` so it maps only to second-level project paths and delegates deep code lookup to CodeGraph.
- [x] Step3: Research AGENTS.md design norms and write the latest AGENTS.md design spec to `D:\wzy\Visionox-Docs_Backup\dev-docs\codex`.
- [x] Step3: Refactor project `AGENTS.md` into stable Context Router and Iteration Router guidance, moving volatile rules into Harness references.
- [x] Step3: Review the refactored `AGENTS.md` against the design spec.
- [x] Step4: Research notable Harness/open-source agent project ideas and write a runnable Harness mechanism design to `D:\wzy\Visionox-Docs_Backup\dev-docs\codex`.
- [x] Step4: Implement the runnable Harness loop in this repo so routing and feedback updates are practical, not just documentation.
- [x] Step4: TDD-wrap `report_download` as a thin Letta client tool path that calls FineReport RPA and passes smoke verification.
- [x] Step4: Update Harness feedback artifacts after the smoke task completes.
- [x] Step5: Split `harness-builder` into two skills for Harness creation and Harness refactoring.
- [x] Step5: Put the final AGENTS.md, Harness architecture, and Harness mechanism into skill configuration/reference files.
- [x] Step5: Validate the new skills.
- [x] Step5: Use the refactor skill to optimize `D:\wzy\Python\vivo-project` until its Harness architecture matches this repo's final optimized architecture.

## Phases

| Phase | Status | Purpose |
|---|---|---|
| 0. Restore and plan | complete | Read invoked skills, restore planning context, and create this isolated plan. |
| 1. Step1 architecture understanding | complete | Inspect `references`, infer current and complete Harness architecture, and output the architecture diagram. |
| 2. Step2 Harness indexes and ARCHITECTURE | complete | Rebuild folder-only indexes and simplify `ARCHITECTURE.md` to two-level routing. |
| 3. Step3 AGENTS.md research and refactor | complete | Research current conventions, write external spec, move stable/volatile guidance to proper locations, and review. |
| 4. Step4 runnable Harness and report_download TDD | complete | Design and implement routing/feedback mechanics, then TDD the `report_download` Letta wrap-skill smoke path. |
| 5. Step5 Harness skill split and vivo-project migration | complete | Create/refactor Harness skills, validate them, and apply the refactor skill to `vivo-project`. |
| 6. Final verification and delivery | complete | Run focused tests/checks, inspect diffs, and summarize outputs and risks. |

## TDD Strategy
- For documentation/Harness routing changes, use behavior-style checks: path existence, index invariants, link validation, and AGENTS routing review.
- For `report_download` Letta wrapping, test through public runtime interfaces and registry exports rather than internal call order.
- Mock only system boundaries such as Letta service, browser/RPA, filesystem-heavy report downloads, and time.
- Keep each test cycle vertical: add one failing test, implement the minimum, run the focused test, then proceed.

## Decisions Made
| Decision | Rationale |
|---|---|
| Use an isolated `.planning/2026-06-25-refactor-harness` plan | Existing root and active plans are completed work for other goals; isolation avoids mixing task state. |
| Treat root planning files as history, not the active plan | They contain completed Daily Report, Letta, and Agent architecture sections. |
| Use manual plan-file creation after init script mismatch | PowerShell init only supports legacy root mode and Bash is unavailable on this host. |
| Let CodeGraph handle code structure lookup before grep/read | Required by project instructions because `.codegraph/` exists. |

## Errors Encountered
| Error | Attempt | Resolution |
|---|---|---|
| `init-session.ps1 'refactor-harness'` did not create an isolated plan | 1 | Inspected scripts and found only Bash supports slug mode. |
| `bash` unavailable on this Windows host | 1 | Created isolated planning files manually with `apply_patch`. |
| `git status -- <external-file>` failed because the file is outside the repo | 1 | Verify external deliverables with `Test-Path` and content reads instead of Git. |
