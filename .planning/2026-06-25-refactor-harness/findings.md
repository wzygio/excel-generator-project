# Harness Refactor Findings

## Requirements
- The user moved the Harness into `references` and wants the architecture understood, completed, and made runnable.
- `index.md` files should list folder paths only, not individual files.
- `ARCHITECTURE.md` should only go down to second-level project paths; detailed code tracing belongs to CodeGraph.
- `AGENTS.md` should be stable across business/design changes and should act as a Context Router plus Iteration Router.
- Volatile rules should move out of `AGENTS.md` into Harness reference folders.
- The runnable Harness mechanism must support both mounting/progressive disclosure and feedback/iteration loops.
- `report_download` should be wrapped into a thin Letta client tool path that calls FineReport RPA and can pass smoke verification.
- The old `harness-builder` skill should become two skills: one for Harness creation and one for Harness refactoring.
- The final Harness architecture should be applied to `D:\wzy\Python\vivo-project`.

## Initial Context
- Root `task_plan.md`, `findings.md`, and `progress.md` exist and contain completed history from Daily Report, Letta, and Agent architecture work.
- `.planning/.active_plan` previously pointed at `2026-06-24-refactor-daily-report-task2`, which is complete and unrelated to this task.
- `.codegraph/` exists, so source-code understanding should use CodeGraph first.
- `docs/dev_prompt/active/refactor-harness.md` is the active task source.
- `planning-with-files`, `tdd`, `anysearch`, `harness-builder`, `skill-creator`, and `write-a-skill` instructions have been read.
- Initial `git status --short` for this task shows existing user changes: modified `ARCHITECTURE.md`, deleted `references/final_work.md`, untracked `docs/dev_prompt/active/refactor-harness.md`, untracked `references/retrospective.md`, and this new planning directory.
- Current `references` top-level folders are `references/plan_references`, `references/dev_references`, and `references/test_references`.
- Only one `index.md` currently exists under `references`: `references/plan_references/design/index.md`.
- Current reference contents include design/system agent contracts, module design docs, feature design docs, table templates/schemas/figures, and `test_references/observability.md`.
- `references/plan_references/design/index.md` still points to old `docs/...` paths, so Step2 must rebuild indexes around the new `references` tree.
- `references/test_references/observability.md` exists and is a useful Test-Reference entrypoint, but it still mentions old `docs/generated/` for generated Harness audits.
- `references/retrospective.md` is the current Harness garbage-collection/feedback artifact and maps to the image's Iteration/feedback loop, but its old cleanup checklist still references `docs/design`, `docs/plans`, and `docs/generated`.
- External output directory for Step1 exists: `D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev`.
- Step2 normalized design docs from `references/plan_references/design` into `references/design`, including correcting `module_disign` to `module_design`.
- Step2 added folder-only indexes for root references, project info/config, design, plans, dev references, generated references, and test references.
- Step2 rewrote `ARCHITECTURE.md` into a shallow two-level map. The document now avoids deep file/module paths and explicitly delegates symbol/file tracing to CodeGraph.
- Stale route references still remain in `AGENTS.md`, `references/test_references/observability.md`, `references/retrospective.md`, and several migrated design docs. These belong to Step3 routing/spec cleanup.
- Step3 external spec is `D:\wzy\Visionox-Docs_Backup\dev-docs\codex\agents-md-design-spec.md`.
- Step3 root AGENTS structure now matches the spec: Project Overview, Code Intelligence Policy, Context Router, Iteration Router, and Safety Boundary.
- Step3 moved volatile details into Harness references: `references/design/system_design/rules_boundary.md`, `references/dev_references/coding_spec/coding_conventions.md`, `references/dev_references/restrictions/safety_rules.md`, `references/test_references/tools/project_commands.md`, `references/test_references/methods/validation.md`, and `references/project-info/source_of_truth.md`.
- Step4 external mechanism design is `D:\wzy\Visionox-Docs_Backup\dev-docs\codex\runnable-harness-mechanism.md`.
- Step4 runnable Harness mechanism is `scripts/harness_check.py`; it validates AGENTS router shape, folder-only indexes, shallow architecture, and required Harness paths.
- Step4 generated Harness audit is `references/generated/harness-check.json`.
- Step4 `report_download` Letta path is a thin `yield_report_download` client tool that maps to `report_download` Skill and is documented as wrapping FineReport RPA.
- Step5 new skill paths: `C:\Users\V0141351\.agents\skills\harness-creator` and `C:\Users\V0141351\.agents\skills\harness-refactor`.
- Step5 skill configs: `references/harness_creator_config.json` and `references/harness_refactor_config.json`.
- Step5 target repo `D:\wzy\Python\vivo-project` now passes the same generated Harness check and has legacy Harness inputs archived under `references/generated/legacy-harness`.
- The target repo had pre-existing dirty log/resource changes before migration; the Harness work did not touch those files.

## Visual Findings From Step1 Images
- The complete Harness model is `Harness: Reference`.
- `AGENTS.md` is outside the reference tree and contains three stable sections: `Project Overview`, `Context Router`, and `Iteration Router`.
- `Plan-Reference: 制定计划` has two branches:
  - `Project Info`: project architecture at `ARCHITECTURE.md`, project information at `references/project-info`, and project configuration at `references/project-conf`.
  - `Design`: global design at `references/DESIGN.md`, design index at `references/design/index.md`, system design at `references/design/system_design`, module design at `references/design/module_design`, and feature design at `references/design/feat_design`.
- `Dev-Reference: 代码开发` has four branches:
  - `Dev-Plan`: plan template at `references/PLANS.md`, plan index at `references/exec-plans/index.md`, active plans at `references/plans/active/*.md`, and completed plans at `references/plans/completed/*.md`.
  - `Dev-Workflow`: implementation guidance, audit/optimization guidance, and iteration/feedback garbage collection. Audit dimensions include security, performance, reliability, simplicity, and maintainability. Paths shown include `references/dev_references/SECURITY.md`, `references/dev_references/QUALITY_SC...`, and `references/dev_references/RELIABILITY.md`.
  - `Coding-Spec`: personal coding conventions at `references/dev_references/coding_spec` and restrictions at `references/dev_references/restrictions`.
  - `Dev-Guidance`: generated agent memory at `references/generated/`.
- `Test-Reference: 执行测试` has four branches:
  - `Acceptance Spec`: definition of done and checklist/feature list.
  - `Test Method`: unit/integration tests with `pytest`, plus browser tests via Playwright MCP/browser smoke.
  - `Test Tools`: executable environment and observability system.
  - `Debug Router`: Codex self-decision/debug routing.
- The image reinforces the user's premise: Harness content should be references organized by development phase, while `AGENTS.md` is the stable router rather than a business-rule container.

## Research Findings
- AGENTS.md official/open format guidance frames the file as a simple, predictable "README for agents": place it at repo root, cover what matters for setup/build/test/style, and use nested AGENTS files when scope differs.
- OpenAI Codex AGENTS.md guidance emphasizes repository expectations, setup, test commands, and code-style instructions that Codex loads as custom instructions.
- Google Jules documents AGENTS.md as an instruction file Jules reads before working, including setup, testing, environment, and coding guidance.
- GitHub Copilot repository custom instructions use `.github/copilot-instructions.md`, but the same design principle applies: keep instructions concise, project-specific, and focused on stable coding/workflow guidance.
- Aider's conventions files show an adjacent pattern: repository-specific coding conventions should be explicit but should avoid becoming a broad documentation dump.
- A June 14, 2026 arXiv paper on AGENTS/CLAUDE configuration smells identifies common issues including lint leakage, context bloat, skill leakage, and conflicting instructions. This supports moving duplicate lint/style/safety details out of the root router and into targeted references.
- AGENTS.md design implication for this repo: keep root `AGENTS.md` stable and short, make it a Context Router and Iteration Router, and route volatile business/design/coding/testing rules into `references`.
- Step4 Harness research: Open SWE frames a coding-agent Harness as orchestration, tools, and middleware layered on an agent framework; useful idea is "compose on existing frameworks rather than fork everything."
- OpenHands emphasizes a production Harness around reliable tool calling, runtime/sandbox control, and developer control surfaces.
- SWE-agent and mini-swe-agent emphasize that a useful Harness can stay small if it provides a clear tool loop and task environment instead of a huge config monorepo.
- LangGraph/LangChain docs emphasize durable execution, persistence, streaming, human-in-the-loop, and low-level orchestration control.
- Aider conventions reinforce keeping guidance files small and explicitly included rather than bloated.
- Step4 design implication: this repo's runnable Harness should be lightweight: a root router, reference indexes, a local validation/check script, and an iteration/retrospective update loop. It should not become a full alternate Agent platform.

## Technical Decisions
| Decision | Rationale |
|---|---|
| Track this task under `.planning/2026-06-25-refactor-harness` | Keeps the multi-day, multi-repo task separate from completed root plan history. |
| Use behavior checks for docs | The TDD skill emphasizes public behavior; for Harness docs, behavior means discoverability, route correctness, and index invariants. |
| Keep external/web research summaries in `findings.md` | Planning skill warns against putting untrusted fetched content into `task_plan.md`. |

## Issues Encountered
| Issue | Resolution |
|---|---|
| PowerShell planning init lacks slug mode | Manual isolated plan creation with `apply_patch`. |
| Bash is not installed | Avoid Bash-dependent planning scripts for this task. |

## Resources
- Task prompt: `docs/dev_prompt/active/refactor-harness.md`
- Planning skill: `C:\Users\V0141351\.agents\skills\planning-with-files\SKILL.md`
- TDD skill: `C:\Users\V0141351\.agents\skills\tdd\SKILL.md`
- Harness Builder skill: `C:\Users\V0141351\.agents\skills\harness-builder\SKILL.md`
- Skill Creator: `C:\Users\V0141351\.codex\skills\.system\skill-creator\SKILL.md`
- AGENTS.md open format: https://agents.md/
- AGENTS.md GitHub repository: https://github.com/agentsmd/agents.md
- OpenAI Codex AGENTS.md guide: https://developers.openai.com/codex/guides/agents-md
- Google Jules AGENTS.md docs: https://jules.google/docs/concepts/agents-md/
- GitHub Copilot repository custom instructions: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- Aider conventions: https://aider.chat/docs/usage/conventions.html
- Configuration smells in AGENTS.md files: https://arxiv.org/abs/2606.15828
- AGENTS.md effectiveness study: https://arxiv.org/abs/2602.11988
- AGENTS.md efficiency study: https://arxiv.org/abs/2601.20404
- Open SWE: https://github.com/langchain-ai/open-swe
- OpenHands: https://www.openhands.dev/
- SWE-agent: https://swe-agent.com/latest/
- mini-swe-agent: https://github.com/SWE-agent/mini-swe-agent
- LangGraph: https://github.com/langchain-ai/langgraph
- LangChain framework/runtime/harness concepts: https://docs.langchain.com/oss/python/concepts/products
