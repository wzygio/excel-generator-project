# Architecture

## Project Purpose

An OLED yield-report assistant that turns user requests into traceable TaskSpecs, executes approved Skills, and delivers auditable Excel report outputs.

## Runtime Flow

```text
User request -> TaskSpec -> Agent Runtime -> Skill Tool -> SkillResult
             -> Trace / Memory / Output
```

The Runtime routes report download, Excel analysis, and report generation to constrained Skills. FineReport browser automation and Excel IO remain at Skill or infrastructure boundaries; domain rules remain explicit and testable.

## Agent Workflow

| Stage | Purpose | Artifacts | References |
|---|---|---|---|
| Design | Capture requirements and maintain product specifications. | `.scratch/`, `docs/PRD/` | `references/design_references/` |
| Plan | Turn approved requirements into traceable execution phases. | `.planning/` | — |
| Dev/Test | Implement behavior and prove it through focused then broad verification. | `app/`, `src/`, `tests/` | `references/dev_references/`, `references/test_references/` |
| Summary | Record durable architectural decisions and evolve Harness guidance. | `docs/ADR/` | `references/summary_references/` |

## Project Map

| Path | Role |
|---|---|
| `app/` | Legacy application entrypoints and compatibility helpers. |
| `config/` | Project configuration inputs. |
| `data/` | Local data and Agent memory caches. |
| `docs/` | Durable requirements, decisions, retained development material, and agent configuration. |
| `output/` | Rebuildable runtime output; not source-of-truth project knowledge. |
| `references/` | Canonical Harness guidance and generated audits. |
| `resources/` | User-provided source workbooks, templates, and RPA results. |
| `scripts/` | Executable scripts and workbench adapters. |
| `specs/` | TaskSpec templates and run records. |
| `src/` | Current Python domain, Agent, Skill, application, and infrastructure implementation. |
| `tests/` | Automated verification entrypoints. |
| `ui/` | Frontend entrypoints. |

## Boundaries

- The Agent orchestrates approved Skills and task state; Skills own stable report capabilities and their input/output contracts.
- User-provided resources are read-only inputs. Rebuildable runtime artifacts are not source-of-truth project knowledge.
- UI presentation, browser automation, and external integrations stay outside core domain behavior.

## Verification

- Run focused unit or integration tests for changed Agent, Skill, report, and adapter boundaries.
- Run the Harness checker after routing or reference-structure changes.
- Use browser smoke checks only when portal or UI flows change.
