# data_analysis

## When To Use
Use this skill when Codex needs to answer data questions from downloaded yield-report Excel files.

## Inputs
- `question`: Natural-language analysis request.
- `report_refs`: Upstream artifacts or paths from `report_download`.
- `file_path` / `file_name`: Optional explicit source file.
- `product_models`: Product filters.
- `time_range`: Optional `{start, end}` mapping.
- `metrics`: Target metrics such as `CT良率`.
- `analysis_intent`: Trend, comparison, ranking, exception analysis, or summary.
- `confirmed_memory_ids`: Reserved for explicit memory reuse.

## Outputs
- `data.result_text`: human-readable analysis.
- `data.workflow_steps`: observable pipeline steps.
- Excel artifact for the actual source file used.
- Pending memory candidate when the analysis succeeds.

## Workflow
1. Compose or accept the analysis question.
2. Resolve the source file from explicit input or upstream artifacts.
3. Reuse `AnalysisOrchestrator`.
4. Return unified `SkillResult`.

## Error Handling
- `data_analysis.execution.failed`: parsing, file resolution, schema extraction, strategy selection, or execution failed.

## Examples
- "请分析M678近一周的日度CT良率变化趋势".
- "对刚下载的月周天报表做CT良率趋势分析".
