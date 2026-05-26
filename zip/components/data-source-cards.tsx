"use client"

import { useState } from "react"
import { ChevronDown, Database, FileSpreadsheet } from "lucide-react"
import { cn } from "@/lib/utils"

interface DataSource {
  name: string
  type: "EDA" | "FineReport"
  successRate: number
  rows: number
  latency: string
  lastFetch: string
}

const SOURCES: DataSource[] = [
  {
    name: "EDA 自动化流水线",
    type: "EDA",
    successRate: 99.4,
    rows: 12847,
    latency: "1.82s",
    lastFetch: "00:42 前",
  },
  {
    name: "帆软报表接口",
    type: "FineReport",
    successRate: 97.1,
    rows: 3216,
    latency: "2.41s",
    lastFetch: "00:42 前",
  },
]

export function DataSourceCards() {
  const [open, setOpen] = useState(false)

  return (
    <section className="overflow-hidden rounded-xl border border-stone-200/70 bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-stone-50/60"
      >
        <span className="font-mono text-[10px] text-stone-400">01</span>
        <span className="text-[13px] font-medium text-stone-900">数据源连接</span>
        <div className="ml-1 flex items-center gap-1">
          {SOURCES.map((s) => (
            <span key={s.name} className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          ))}
        </div>
        <span className="text-[11px] text-stone-500">2/2 通道正常</span>
        <span className="ml-auto font-mono text-[11px] text-stone-400">
          {SOURCES.reduce((a, b) => a + b.rows, 0).toLocaleString()} rows
        </span>
        <ChevronDown
          className={cn("h-3.5 w-3.5 text-stone-400 transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div className="grid grid-cols-1 gap-px border-t border-stone-100 bg-stone-100 sm:grid-cols-2">
          {SOURCES.map((s) => (
            <SourceRow key={s.name} source={s} />
          ))}
        </div>
      )}
    </section>
  )
}

function SourceRow({ source }: { source: DataSource }) {
  const Icon = source.type === "EDA" ? Database : FileSpreadsheet

  return (
    <div className="flex flex-col gap-3 bg-white p-5">
      <div className="flex items-center gap-2.5">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-stone-50 text-stone-700">
          <Icon className="h-3.5 w-3.5" />
        </div>
        <span className="text-[13px] font-medium text-stone-900">{source.name}</span>
        <span className="ml-auto rounded-md bg-emerald-50 px-1.5 py-0.5 font-mono text-[10px] font-medium text-emerald-700">
          OK
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Metric label="成功率" value={`${source.successRate}%`} accent />
        <Metric label="行数" value={source.rows.toLocaleString()} />
        <Metric label="延迟" value={source.latency} />
      </div>

      <div className="h-1 overflow-hidden rounded-full bg-stone-100">
        <div
          className="h-full rounded-full bg-emerald-500"
          style={{ width: `${source.successRate}%` }}
        />
      </div>
    </div>
  )
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-stone-400">{label}</div>
      <div
        className={cn(
          "mt-0.5 font-mono text-sm font-semibold tabular-nums",
          accent ? "text-emerald-600" : "text-stone-900",
        )}
      >
        {value}
      </div>
    </div>
  )
}
