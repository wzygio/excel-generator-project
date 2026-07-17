# daily_report

## When To Use
Use this skill when Codex or Agent Runtime needs to run the full OLED daily-report workbook workflow.

This skill is a thin Python adapter around the user-facing `$daily-report-generator` CLI. It does not contain daily-report business rules and does not call or expose per-step wrapper skills directly.

Do not duplicate the generator's business rules here.

## Inputs
- `report_date`: Report date.
- `generator_root`: Optional explicit installation override for the public skill.
- `generator_workspace`: Optional compatibility run-root override. When omitted, the public CLI uses its own installed skill root.
- `output_dir`: Optional generated workbook directory override. The Agent default comes from validated project configuration.
- `generator_now`: Optional explicit deterministic run time. `report_date` does not synthesize or replace it.
- Other request fields are accepted for compatibility with existing specs and UI payloads, but this wrapper does not interpret daily-report business data.

## Outputs
- Excel artifact: the generated daily report workbook.
- `data.runtime`: `daily-report-generator`.
- `data.generator_root`: resolved generator skill root.
- `data.output_dir`: resolved generated workbook directory.
- `data.workflow`: generator mod ids executed in order.
- `data.native_result`: raw JSON returned by the external generator CLI.

## Workflow
1. Resolve Agent integration settings through the project's Pydantic configuration.
2. Run the public `scripts/daily_report_cli.py run --output-dir <agent-output> --mode write` entry point with the configured generator Python executable (or the wrapper interpreter when it is unset). Pass `--workspace` only for an explicit compatibility override.
3. Parse the generator JSON result.
4. Return the generated workbook as the Excel artifact.

## Error Handling
- `daily_report.native_pipeline.failed`: generator CLI, workbook generation, JSON parsing, or filesystem failure.
