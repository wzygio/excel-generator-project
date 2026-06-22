# anomaly_monitor

## When To Use

Use this Skill for the fixed anomaly-monitor workflow: read daily anomaly candidates, judge real HL anomalies, and generate HL notification drafts.

## Inputs

- `report_date`: optional report date.
- `product_models`: optional product filter. If omitted, the Skill reads the daily shipping
  products from `spotfire`.
- `source_files`: source aliases such as `data_source_dir`, `spotfire`, `hl_raw`,
  `batch_yield`, `mwdl_raw`, `ct_yield`, `defect_group_dict`, and optional `ct_exception`.
  By default `data_source_dir` is `//10.71.7.15/大数据共享/12.良率监控日报自动化`.
- `initial_rows`, `ct_exception_rows`, `batch_history_rows`, `detail_rows`: inline rows for tests or prepared upstream steps.
- `mode`: `detect`, `draft_notice`, `record`, or `full`.
- `write_ledgers`: accepted but currently gated and disabled by default.
- `push_notifications`: when true, posts the formatted HL anomaly payload to the
  V-Agent webhook configured by `YIELD_REPORT_V_AGENT_WEBHOOK_URL`. Missing webhook
  configuration skips delivery and keeps local artifacts successful.

## Outputs

- JSON artifact: `anomaly_monitor_result.json`.
- Markdown artifact: `anomaly_monitor_summary.md`.
- Structured `verdicts`, `hl_anomalies`, `real_anomalies`, `notice_drafts`, and `blocked_items`.
- `source_summary`: row counts, source tables, and compact date windows for loaded sources.
- `source_evidence`: source-backed rows supporting each real anomaly decision.

## Workflow

1. Load and normalize sources.
2. Build the daily anomaly candidate table from `hl_data.csv + batch_yield_data.csv`
   using the reference anomaly-monitor Spotfire replication logic.
3. Add missing LOT-level candidates from `mwdl_data.csv` when a defect is absent from
   `hl_data.csv` but still exists in the raw source tables.
4. Build CT detail concentration rows from `ct_yield_data.csv` (`ng_qty > 0`) and parse
   Lot / Map / Map-row / Sheet / Glass dimensions.
5. Apply the base gate: batch loss `> 0.1%`, lot output `> 20%`, multiplier `> 30%`,
   and NG count `> 20`; strong concentration can pass with daily loss `> 0.1%` even
   when lot output is low.
6. Mark rows as HL when they have concentration evidence or exceed the CT historical
   max from `mwdl_data.csv`.
7. Classify CT rows as `真实异常` and non-CT rows as `当站超规`, then build notice drafts
   and traceable artifacts.

## Error Handling

- `anomaly_monitor.input.missing_initial_rows`: no daily anomaly initial rows were provided.
- `ct_exception` is never used as a daily candidate fallback; it is only evidence/history.
- Source read failures are returned as warnings when enough inline or CSV-backed rows are still available.

## Examples

```yaml
workflow:
  - id: run_anomaly_monitor
    skill: anomaly_monitor
    input:
      report_date: "2026-06-01"
      product_models: ["M678"]
      mode: detect
      source_files:
        data_source_dir: //10.71.7.15/大数据共享/12.良率监控日报自动化
        spotfire: D:/wzy/工作-值班工作/相关文件/resources/spotfire.xlsx
```
