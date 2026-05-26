"use client"

import {
  Sparkles,
  CircleCheck,
  CircleDot,
  Play,
  Database,
  FileSpreadsheet,
  Brain,
  Settings2,
  History,
  LayoutDashboard,
  Loader2,
} from "lucide-react"
import { cn } from "@/lib/utils"

type AgentStage = "idle" | "login" | "fetching" | "processing" | "ready"

interface AgentStatusPanelProps {
  stage: AgentStage
  running: boolean
  onTrigger: () => void
}

const STAGES: { key: AgentStage; label: string; hint: string; icon: any }[] = [
  { key: "login", label: "内网登录", hint: "SSO 鉴权", icon: CircleDot },
  { key: "fetching", label: "数据抓取", hint: "EDA · FineReport", icon: Database },
  { key: "processing", label: "LLM 分析", hint: "异常归因", icon: Brain },
  { key: "ready", label: "日报就绪", hint: "可导出", icon: CircleCheck },
]

export function AgentStatusPanel({ stage, running, onTrigger }: AgentStatusPanelProps) {
  const stageIndex = STAGES.findIndex((s) => s.key === stage)

  return (
    <aside className="flex h-full w-full flex-col gap-6 border-r border-stone-200/70 bg-white p-6 lg:w-72">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-stone-900 text-white">
          <Sparkles className="h-4 w-4" strokeWidth={2} />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-tight text-stone-900">Yield Agent</div>
          <div className="text-[11px] font-medium text-stone-500">良率日报 · v2.1</div>
        </div>
      </div>

      {/* Status pill */}
      <div className="flex items-center gap-2 rounded-lg border border-stone-200/70 bg-stone-50/60 px-3 py-2">
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            running ? "animate-pulse bg-amber-500" : stage === "ready" ? "bg-emerald-500" : "bg-stone-400",
          )}
        />
        <span className="text-[11px] font-medium text-stone-700">
          {running ? "运行中" : stage === "ready" ? "已完成" : "待命"}
        </span>
        <span className="ml-auto font-mono text-[10px] text-stone-400">2026-05-26</span>
      </div>

      {/* CTA */}
      <button
        onClick={onTrigger}
        disabled={running}
        className={cn(
          "flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-medium transition-all",
          running
            ? "cursor-not-allowed bg-stone-100 text-stone-400"
            : "bg-stone-900 text-white hover:bg-stone-800 active:scale-[0.99]",
        )}
      >
        {running ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            正在生成…
          </>
        ) : (
          <>
            <Play className="h-3.5 w-3.5 fill-current" />
            执行全自动抓取
          </>
        )}
      </button>

      {/* Pipeline */}
      <div className="flex flex-col gap-0.5">
        <span className="mb-2 px-1 text-[10px] font-medium uppercase tracking-[0.14em] text-stone-400">
          执行流水线
        </span>
        {STAGES.map((s, i) => {
          const done = stageIndex > i || stage === "ready"
          const active = stageIndex === i && running
          return (
            <div key={s.key} className="relative flex gap-3">
              {i < STAGES.length - 1 && (
                <span
                  className={cn(
                    "absolute left-[17px] top-9 bottom-0 w-px",
                    done ? "bg-emerald-400" : "bg-stone-200",
                  )}
                />
              )}
              <div
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors",
                  active && "bg-stone-900 text-white",
                  done && !active && "bg-emerald-50 text-emerald-600",
                  !active && !done && "bg-stone-50 text-stone-400",
                )}
              >
                {active ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : done ? (
                  <CircleCheck className="h-4 w-4" />
                ) : (
                  <s.icon className="h-3.5 w-3.5" />
                )}
              </div>
              <div className="flex flex-col gap-0.5 pb-4 pt-1.5">
                <span
                  className={cn(
                    "text-[13px] font-medium",
                    !active && !done && "text-stone-400",
                    (active || done) && "text-stone-900",
                  )}
                >
                  {s.label}
                </span>
                <span className="text-[11px] text-stone-500">{s.hint}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Nav */}
      <nav className="mt-auto flex flex-col gap-0.5 border-t border-stone-100 pt-4 text-sm">
        <NavItem icon={LayoutDashboard} label="工作台" active />
        <NavItem icon={History} label="历史日报" badge="128" />
        <NavItem icon={FileSpreadsheet} label="数据源" />
        <NavItem icon={Settings2} label="Agent 配置" />
      </nav>
    </aside>
  )
}

function NavItem({
  icon: Icon,
  label,
  active,
  badge,
}: {
  icon: any
  label: string
  active?: boolean
  badge?: string
}) {
  return (
    <button
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] font-medium transition-colors",
        active ? "bg-stone-100 text-stone-900" : "text-stone-500 hover:bg-stone-50 hover:text-stone-900",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="flex-1">{label}</span>
      {badge && (
        <span className="rounded-md bg-stone-100 px-1.5 py-0.5 font-mono text-[10px] font-medium text-stone-500">
          {badge}
        </span>
      )}
    </button>
  )
}
