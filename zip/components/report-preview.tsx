"use client"

import { Download, FileText, Calendar, TrendingUp, TrendingDown, AlertTriangle, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

interface ReportRow {
  fab: string
  product: string
  bp: number
  pull: number
  actual: number
  gap: number
  estimate: number
  risk: "正常" | "风险品" | "释放"
  exception: string
}

const ROWS: ReportRow[] = [
  { fab: "ARRAY", product: "V3-65″ UHD", bp: 92.5, pull: 94.0, actual: 93.8, gap: 1.3, estimate: 93.2, risk: "正常", exception: "—" },
  { fab: "ARRAY", product: "V3-55″ QLED", bp: 91.0, pull: 92.5, actual: 90.2, gap: -0.8, estimate: 90.7, risk: "风险品", exception: "CT-Mura 异常" },
  { fab: "OLED", product: "OLED-77″ G2", bp: 88.0, pull: 90.0, actual: 89.4, gap: 1.4, estimate: 89.1, risk: "正常", exception: "—" },
  { fab: "OLED", product: "OLED-48″ C3", bp: 87.5, pull: 89.0, actual: 86.1, gap: -1.4, estimate: 86.5, risk: "风险品", exception: "Pixel-Defect 上升" },
  { fab: "TP", product: "TP-32″ Pro", bp: 95.0, pull: 96.0, actual: 95.7, gap: 0.7, estimate: 95.5, risk: "释放", exception: "—" },
  { fab: "TP", product: "TP-27″ G", bp: 94.0, pull: 95.0, actual: 94.6, gap: 0.6, estimate: 94.4, risk: "正常", exception: "—" },
]

export function ReportPreview({ ready }: { ready: boolean }) {
  return (
    <section className="flex h-full flex-col overflow-hidden rounded-2xl border border-stone-200/70 bg-white">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-stone-900 text-white">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold tracking-tight text-stone-900">
                V3 屏体良率日报
              </h2>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium",
                  ready ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    ready ? "bg-emerald-500" : "bg-stone-400",
                  )}
                />
                {ready ? "已生成" : "等待生成"}
              </span>
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-[12px] text-stone-500">
              <Calendar className="h-3 w-3" />
              <span>2026-05-26 · DeepSeek-V3 + Gemini 2.0 协同</span>
            </div>
          </div>
        </div>
        <button
          disabled={!ready}
          className={cn(
            "flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all",
            ready
              ? "bg-emerald-600 text-white shadow-sm shadow-emerald-600/20 hover:bg-emerald-700 active:scale-[0.99]"
              : "cursor-not-allowed bg-stone-100 text-stone-400",
          )}
        >
          <Download className="h-4 w-4" />
          导出 CSV
        </button>
      </header>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 gap-px border-b border-stone-100 bg-stone-100 sm:grid-cols-4">
        <Kpi label="平均良率" value="91.6%" delta="+0.4" up ready={ready} />
        <Kpi label="风险品数量" value="2" delta="-1" up ready={ready} />
        <Kpi label="新增异常" value="2" delta="+2" warn ready={ready} />
        <Kpi label="目标 Gap" value="-0.12pt" delta="收敛" up ready={ready} />
      </div>

      {/* AI Summary */}
      <div className="border-b border-stone-100 px-6 py-4">
        <div className="flex items-start gap-3 rounded-xl border border-amber-100/80 bg-gradient-to-br from-amber-50/60 to-stone-50/40 p-4">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white shadow-sm ring-1 ring-amber-100">
            <Sparkles className="h-3.5 w-3.5 text-amber-600" />
          </div>
          <div>
            <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-amber-700">
              AI Summary
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-stone-700">
              当日 ARRAY 厂良率整体达成 BP 目标，<span className="font-medium text-stone-900">V3-55″ QLED</span> 受
              CT-Mura 异常影响，Gap 值为
              <span className="font-mono font-semibold text-rose-600"> -0.8pt</span>，建议持续监控并安排片源重测。OLED-48″
              C3 Pixel-Defect 上升，已进入风险管控。
            </p>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-white">
            <tr className="border-b border-stone-100">
              {["厂别", "产品型号", "BP", "提拉", "实际", "Gap", "预估", "风险", "异常"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-wider text-stone-500"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row, i) => (
              <tr
                key={i}
                className={cn(
                  "border-b border-stone-50 transition-colors hover:bg-stone-50/60",
                  !ready && "opacity-40",
                )}
              >
                <td className="px-4 py-3">
                  <span className="rounded-md bg-stone-100 px-2 py-0.5 font-mono text-[11px] font-medium text-stone-700">
                    {row.fab}
                  </span>
                </td>
                <td className="px-4 py-3 font-medium text-stone-900">{row.product}</td>
                <td className="px-4 py-3 font-mono text-stone-500 tabular-nums">{row.bp.toFixed(1)}%</td>
                <td className="px-4 py-3 font-mono text-stone-500 tabular-nums">{row.pull.toFixed(1)}%</td>
                <td className="px-4 py-3 font-mono font-semibold text-stone-900 tabular-nums">
                  {row.actual.toFixed(1)}%
                </td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 font-mono text-[12px] font-semibold tabular-nums",
                      row.gap >= 0 ? "text-emerald-600" : "text-rose-600",
                    )}
                  >
                    {row.gap >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                    {row.gap > 0 ? "+" : ""}
                    {row.gap.toFixed(1)}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-stone-500 tabular-nums">{row.estimate.toFixed(1)}%</td>
                <td className="px-4 py-3">
                  <RiskTag risk={row.risk} />
                </td>
                <td className="px-4 py-3 text-stone-600">
                  {row.exception !== "—" ? (
                    <span className="inline-flex items-center gap-1 text-amber-700">
                      <AlertTriangle className="h-3 w-3" />
                      {row.exception}
                    </span>
                  ) : (
                    <span className="text-stone-300">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <footer className="flex items-center justify-between border-t border-stone-100 px-6 py-2.5 text-[11px] text-stone-500">
        <span>共 {ROWS.length} 条记录 · Parquet 已缓存</span>
        <span className="font-mono text-stone-400">SHA-256: 4f2e···c1a8</span>
      </footer>
    </section>
  )
}

function Kpi({
  label,
  value,
  delta,
  up,
  warn,
  ready,
}: {
  label: string
  value: string
  delta: string
  up?: boolean
  warn?: boolean
  ready: boolean
}) {
  return (
    <div className={cn("bg-white px-5 py-4 transition-opacity", !ready && "opacity-50")}>
      <div className="text-[10px] font-medium uppercase tracking-wider text-stone-400">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span
          className={cn(
            "font-mono text-xl font-semibold tabular-nums tracking-tight",
            warn ? "text-amber-700" : "text-stone-900",
          )}
        >
          {ready ? value : "—"}
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-0.5 text-[11px] font-medium",
            up ? "text-emerald-600" : warn ? "text-amber-700" : "text-stone-500",
          )}
        >
          {up ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
          {delta}
        </span>
      </div>
    </div>
  )
}

function RiskTag({ risk }: { risk: "正常" | "风险品" | "释放" }) {
  const styles = {
    正常: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    风险品: "bg-rose-50 text-rose-700 ring-rose-100",
    释放: "bg-stone-100 text-stone-700 ring-stone-200",
  }
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1",
        styles[risk],
      )}
    >
      {risk}
    </span>
  )
}
