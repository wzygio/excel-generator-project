# Module Design Index

## Folder Routes

No child folders yet.

## Read Guidance

| Document | When To Read | Commands |
|---|---|---|
| `yield_report_domain.md` | OLED yield-report domain behavior, report naming, analyzers, or business data flow changes. | Run focused parser/analyzer/report tests. |
| `shared_kernel.md` | Shared config, logging, LLM manager, filesystem, or cross-module infrastructure changes. | Run `uv run pyright` and focused shared-kernel tests. |

## Update Rule

Add module-specific folders when a module grows beyond one design note.
