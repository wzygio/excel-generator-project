# daily_report

## When To Use
Use this skill when Codex or Agent Runtime needs to run the full OLED daily-report workbook workflow.

This skill is a thin Python adapter around the user-facing `$daily-report-generator` CLI. It does not contain daily-report business rules and does not call or expose per-step wrapper skills directly.

Do not duplicate the generator's business rules here.

## Inputs
- `report_date`: Report date.
- `source_files`: Optional alias-to-path mapping. Supported generator aliases are `daily_report_generator_root`, `generator_root`, `orchestrator_root`, `generator_workspace`, `orchestrator_workspace`, and `generator_output_dir`.
- `generator_workspace`: Optional run root. Defaults to the current repo workspace from `RunContext`.
- `output_dir`: Optional generated workbook directory. Defaults to `output/artifacts/reports/generated` under the current repo.
- `generator_now`: Optional deterministic run time, for example `2026-06-15 16:00`.
- Other request fields are accepted for compatibility with existing specs and UI payloads, but this wrapper does not interpret daily-report business data.

## Outputs
- Excel artifact: the generated daily report workbook.
- `data.runtime`: `daily-report-generator`.
- `data.generator_root`: resolved generator skill root.
- `data.output_dir`: resolved generated workbook directory.
- `data.workflow`: generator mod ids executed in order.
- `data.native_result`: raw JSON returned by the external generator CLI.

## Workflow
1. Resolve the repo run root, generated workbook directory, and `$daily-report-generator` root.
2. Run `C:\Users\V0141351\.agents\skills\daily-report-generator\scripts\daily_report_cli.py run --workspace <repo> --output-dir <repo>\output\artifacts\reports\generated --mode write`.
3. Parse the generator JSON result.
4. Return the generated workbook as the Excel artifact.

## Error Handling
- `daily_report.native_pipeline.failed`: generator CLI, workbook generation, JSON parsing, or filesystem failure.
