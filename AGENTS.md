# AGENTS.md / .roorules

This file is the project-level operating manual for coding agents. RooCode reads it as
`.roorules`; other agents may use the same content as a standard `AGENTS.md`.

## Project Overview

This project is an Excel-based OLED yield-report assistant. It downloads FineReport source
reports, analyzes local Excel workbooks, and prepares traceable yield-report outputs through an
Agent-friendly Spec / Skill / Runtime architecture.

This is not a generic BI platform. Prefer explicit, testable, traceable report workflows over
broad automatic inference.

## Harness Map

Keep this root file stable. Do not encode business-module details here when they may change with
implementation work; route to the lower Harness documents instead.

- `ARCHITECTURE.md`: current system shape, module boundaries, runtime flow, and architecture decisions.
- `docs/agent/`: Agent / Skill / Spec contracts.
- `docs/design/index.md`: entrypoint for domain, UI, infrastructure, and architecture design notes.
- `docs/plans/index.md`: long-lived project plans and planning conventions.
- `docs/exec-plans/active/`: current execution plans awaiting or undergoing implementation.
- `docs/exec-plans/completed/`: completed execution plans kept for history.
- `docs/observability.md`: trace, log, test, smoke, and diagnostics entrypoint.
- `docs/generated/`: rebuildable scans, audits, and Harness cleanup reports.
- `specs/`: user-maintainable task specs, templates, and rule contracts; runtime runs stay ignored.
- `.roo/rules-architect/` and `.roo/rules-code/`: RooCode mode-specific Harness rules.
- `tests/`: validation entrypoint.

## Code Intelligence Policy

- Use CodeGraph as the default project code graph. When `.codegraph/` exists, prefer CodeGraph MCP tools or the equivalent `codegraph explore`, `codegraph node`, `codegraph callers`, `codegraph callees`, and `codegraph impact` CLI commands for structural code questions.
- Understand-Anything is temporarily disabled for this project. Do not run the `understand-anything:*` skills, rebuild `.understand-anything/`, or treat Understand-Anything output as the active project graph unless the user explicitly asks to re-enable it.
- If the user explicitly re-enables Understand-Anything, confirm the intended scope first and avoid committing generated graph artifacts unless asked.

## Task Routing

- First read `ARCHITECTURE.md` when changing module ownership, cross-layer flow, or system shape.
- For Agent runtime changes, read `docs/agent/architecture.md` and inspect `src/yield_report/agent/`.
- For Skill changes, read `docs/agent/skill_contract.md`, the target `src/yield_report/skills/*/SKILL.md`, and the related tests under `tests/unit/skills/`.
- For Spec or workflow-template changes, read `docs/agent/spec_contract.md` and `specs/templates/daily_report_spec.yaml`.
- For domain or design behavior, start from `docs/design/index.md` and then read the linked lower-level document.
- For config, LLM, or logging changes, read `docs/design/shared_kernel.md`.
- For FineReport RPA changes, read `docs/prompt/skill-fr_rpa.md` and reuse `fr_web_automation` before writing project-local browser logic.
- For Harness / planning behavior, read `.roo/rules-architect/harness-architecture.md`.
- After coding work, follow `.roo/rules-code/knowledge-summarization.md` and `docs/observability.md`.

## Rules Boundary

Spec-owned rules are stable, repeatable, and user-maintainable. Put them in `specs/templates/`,
`specs/runs/`, or documented spec fields when code already supports the rule.

Examples of spec-owned rules:

- report workflow steps and ordering
- report aliases and required source reports
- product models, dates, filters, and output expectations
- selectable analysis sections and reusable report parameters

Code-owned logic belongs in typed Python modules.

Examples of code-owned logic:

- Excel reading, decryption, validation, and writing
- FineReport automation primitives and file download orchestration
- dataframe transformations and analyzers
- Skill request/result/error/artifact contracts
- security, filesystem, logging, and runtime trace handling

Do not hard-code frequently changing business rules in Python unless the user explicitly asks for
a one-off experiment.

## Commands

```bash
# Start CopilotKit Agent Workbench
cd ui/copilotkit-agent
npm run dev

# Run all tests
uv run pytest tests/ -v --tb=short

# Run current core tests
uv run pytest tests/unit/test_query_parser.py tests/unit/test_data_acquisition_orchestrator.py tests/unit/test_yield_download_service.py tests/unit/test_finereport_client.py -v --tb=short

# Run Agent / Skill tests
uv run pytest tests/unit/agent tests/unit/skills -v --tb=short

# Create a daily-report TaskSpec from a natural-language goal
uv run python scripts/create_daily_report_spec.py --goal "生成 M678 今天良率日报" --print-path

# Execute a TaskSpec and write trace/artifacts under specs/runs/<run_id>/
uv run python scripts/run_task_spec.py --spec specs/runs/<run_id>/spec.yaml --runtime auto

# Quality checks
uv run ruff check .
uv run pyright

# Format only when the task calls for formatting or the touched files need it
uv run ruff format .

# Dependency management
uv sync
uv add <package-name>
uv add --dev <package-name>
```

## Coding Conventions

- Add `from __future__ import annotations` to new Python modules.
- Use type annotations for new functions and methods.
- Update Pydantic config models before changing `config/global.yaml`.
- Keep Core logic mostly pure; browser, Excel, filesystem, and network IO belong in Infrastructure or adapters.
- Use `shared_kernel.infrastructure.llm_handler.llm_manager` for LLM calls; do not instantiate provider clients in business code.
- Keep existing public entrypoints compatible unless the user explicitly asks for a breaking refactor.
- Add dependencies only through `pyproject.toml` and explain why existing dependencies are insufficient.
- Prefer focused tests for parser, selector, Skill contract, file naming, logging, and download behavior.

## Validation

Before finishing, run the smallest relevant verification and report what ran.

- Documentation / Harness only: inspect the diff and verify referenced paths exist.
- Core parser, selector, or business-time changes: run focused `tests/unit/test_*.py` tests, or `uv run pytest tests/unit/ -v --tb=short` for broader risk.
- Agent / Skill / Spec changes: run `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short`.
- FineReport, file loading, or download changes: run related unit tests; add browser/RPA smoke only when the visible or portal flow changed.
- CopilotKit UI changes: backend tests are not enough; run `npm run typecheck`, `npm run build`, and perform a real browser/UI smoke test.
- Config, dependency, or typing-sensitive changes: run `uv run pyright` and `uv run ruff check .`.
- If a verification command cannot run, state the command, the blocker, and the residual risk.

## Safety Rules

- Do not print, commit, or copy secrets from `.env`, credentials, cookies, tokens, or internal portal sessions.
- Do not delete or overwrite user-provided Excel files under `resources/` unless explicitly asked.
- Do not commit runtime outputs from `output/`, `downloads/`, `specs/runs/`, `.pytest_cache/`, `.playwright-*`, or `resources/decrypted_files/`.
- If ignored files are still tracked, verify with `git ls-files -ci --exclude-standard` and remove from the index with `git rm --cached <path>` only when asked.
- Do not leave ad-hoc scripts or logs in the repository root; promote reusable scripts to `scripts/` or keep temporary artifacts in ignored output folders.
- Do not rewrite large modules, public contracts, or file formats unless the task explicitly asks for that scope.
- Preserve unrelated user changes in the working tree.

## Source Of Truth

- Technical stack, dependencies, Python version, build config, and tool config: `pyproject.toml`.
- System architecture: `ARCHITECTURE.md`.
- Agent / Skill / Spec contracts: `docs/agent/`.
- Business boundaries and domain behavior: `docs/design/`.
- FineReport project experience: `docs/prompt/skill-fr_rpa.md`.
- RooCode mode-specific behavior: `.roo/rules-architect/` and `.roo/rules-code/`.
