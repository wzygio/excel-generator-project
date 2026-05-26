"use client"

import { useEffect, useRef, useState } from "react"
import { ChevronDown, Terminal } from "lucide-react"
import { cn } from "@/lib/utils"

export interface LogEntry {
  ts: string
  level: "info" | "success" | "warn" | "ai"
  tag?: string
  text: string
}

export function AgentLogger({ logs, running }: { logs: LogEntry[]; running: boolean }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Auto-open when running
  useEffect(() => {
    if (running) setOpen(true)
  }, [running])

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [logs])

  return (
    <section className="overflow-hidden rounded-xl border border-stone-200/70 bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-stone-50/60"
      >
        <span className="font-mono text-[10px] text-stone-400">02</span>
        <Terminal className="h-3.5 w-3.5 text-stone-700" />
        <span className="text-[13px] font-medium text-stone-900">运行日志</span>
        <span
          className={cn(
            "ml-1 h-1.5 w-1.5 rounded-full",
            running ? "animate-pulse bg-amber-500" : logs.length ? "bg-emerald-500" : "bg-stone-300",
          )}
        />
        <span className="ml-auto font-mono text-[11px] text-stone-400">{logs.length} events</span>
        <ChevronDown
          className={cn("h-3.5 w-3.5 text-stone-400 transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div
          ref={ref}
          className="max-h-72 overflow-y-auto border-t border-stone-100 bg-stone-950 px-5 py-3 font-mono text-[12px] leading-relaxed"
        >
          {logs.length === 0 ? (
            <div className="text-stone-500">$ 等待 Agent 启动…</div>
          ) : (
            logs.map((log, i) => <LogLine key={i} log={log} />)
          )}
          {running && (
            <div className="mt-1 flex items-center gap-2 text-amber-300">
              <span className="inline-block h-3 w-1.5 animate-pulse bg-amber-400" />
              <span className="text-stone-500">正在思考…</span>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function LogLine({ log }: { log: LogEntry }) {
  const colors = {
    info: "text-stone-300",
    success: "text-emerald-300",
    warn: "text-amber-300",
    ai: "text-amber-200",
  }
  const tagColors = {
    info: "bg-stone-800 text-stone-300",
    success: "bg-emerald-500/10 text-emerald-300",
    warn: "bg-amber-500/10 text-amber-300",
    ai: "bg-amber-500/15 text-amber-200",
  }

  return (
    <div className="flex gap-3 py-0.5">
      <span className="shrink-0 select-none text-stone-600">{log.ts}</span>
      {log.tag && (
        <span
          className={cn(
            "shrink-0 rounded px-1.5 py-px text-[10px] font-semibold tracking-wide",
            tagColors[log.level],
          )}
        >
          {log.tag}
        </span>
      )}
      <span className={cn("flex-1 break-all", colors[log.level])}>{log.text}</span>
    </div>
  )
}
