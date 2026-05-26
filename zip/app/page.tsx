"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { AgentStatusPanel } from "@/components/agent-status-panel"
import { DataSourceCards } from "@/components/data-source-cards"
import { AgentLogger, type LogEntry } from "@/components/agent-logger"
import { ReportPreview } from "@/components/report-preview"

type Stage = "idle" | "login" | "fetching" | "processing" | "ready"

const SCRIPT: { stage: Stage; logs: Omit<LogEntry, "ts">[] }[] = [
  {
    stage: "login",
    logs: [
      { level: "info", tag: "[1/3]", text: "正在初始化 Agent Runtime · 加载 global.yaml 配置…" },
      { level: "info", text: "→ 发送静态密文至 SSO 网关 https://sso.corp.local/auth …" },
      { level: "success", tag: "AUTH", text: "捕获会话 ID: JSESSIONID=A8F4D2B1C2E1 · 有效期 30min" },
    ],
  },
  {
    stage: "fetching",
    logs: [
      { level: "info", tag: "[2/3]", text: "建立 EDA 自动化通道 · 拉取 V3 良率汇总表…" },
      { level: "ai", text: "成功下载 yield_v3_summary.csv (12,847 rows · 1.82s)" },
      { level: "info", text: "→ 调用帆软 OpenAPI · /webroot/decision/url?op=fr_dialog…" },
      { level: "success", text: "帆软批次报表落盘 batch_report.csv (3,216 rows · 2.41s)" },
      { level: "warn", text: "CT 异常管理表检测到 2 条新增记录 · 已进入解析队列" },
    ],
  },
  {
    stage: "processing",
    logs: [
      { level: "info", tag: "[3/3]", text: "Parquet 缓存命中率 87% · 跳过冷数据扫描" },
      { level: "ai", tag: "LLM", text: "调用 DeepSeek-V3 进行 Gap 分析 · prompt_tokens=2,418" },
      { level: "ai", text: "→ V3-55″ QLED 触发 -0.8pt Gap · CT-Mura 因子相关性 0.84" },
      { level: "ai", tag: "LLM", text: "调用 Gemini-2.0 进行趋势分析 · 三日均线收敛中" },
      { level: "success", text: "富文本样式注入完成 · sharedStrings.xml 已重写" },
      { level: "success", text: "V3屏体良率日报_20260526.xlsx 已生成 (412 KB)" },
    ],
  },
  {
    stage: "ready",
    logs: [{ level: "success", tag: "DONE", text: "Agent 全流程结束 · 用时 8.42s · 等待用户下载" }],
  },
]

export default function Page() {
  const [stage, setStage] = useState<Stage>("idle")
  const [running, setRunning] = useState(false)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  const clearTimers = () => {
    timers.current.forEach(clearTimeout)
    timers.current = []
  }

  const appendLog = (l: Omit<LogEntry, "ts">) => {
    const ts = new Date().toLocaleTimeString("en-GB", { hour12: false })
    setLogs((prev) => [...prev, { ...l, ts }])
  }

  const trigger = useCallback(() => {
    if (running) return
    clearTimers()
    setLogs([])
    setRunning(true)
    setStage("idle")

    let delay = 200
    SCRIPT.forEach((step) => {
      timers.current.push(setTimeout(() => setStage(step.stage), delay))
      delay += 300
      step.logs.forEach((l) => {
        timers.current.push(setTimeout(() => appendLog(l), delay))
        delay += 600
      })
      delay += 300
    })

    timers.current.push(
      setTimeout(() => {
        setRunning(false)
        setStage("ready")
      }, delay),
    )
  }, [running])

  useEffect(() => () => clearTimers(), [])

  const reportReady = stage === "ready" && !running

  return (
    <div className="flex min-h-screen flex-col bg-stone-50 lg:flex-row">
      <AgentStatusPanel stage={stage} running={running} onTrigger={trigger} />

      <main className="flex flex-1 flex-col">
        {/* Top bar */}
        <header className="flex items-center justify-between gap-4 border-b border-stone-200/70 bg-white px-6 py-4">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-stone-400">
              Yield Intelligence · Daily
            </div>
            <h1 className="mt-1 text-lg font-semibold tracking-tight text-stone-900">
              良率日报智能体工作台
            </h1>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-stone-900 text-xs font-medium text-white">
            YR
          </div>
        </header>

        {/* Body */}
        <div className="flex flex-1 flex-col gap-3 p-6">
          {/* Hero: Report */}
          <ReportPreview ready={reportReady} />

          {/* Collapsed dev panels */}
          <DataSourceCards />
          <AgentLogger logs={logs} running={running} />
        </div>
      </main>
    </div>
  )
}
