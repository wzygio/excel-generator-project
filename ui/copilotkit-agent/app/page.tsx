"use client";

import { useMemo, useState } from "react";
import { z } from "zod";
import {
  AlertCircle,
  BarChart3,
  Brain,
  CheckCircle2,
  ClipboardList,
  DatabaseZap,
  Download,
  FileSpreadsheet,
  Loader2,
  Play,
  RotateCcw,
  Send,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  CopilotSidebar,
  useConfigureSuggestions,
  useFrontendTool,
} from "@copilotkit/react-core/v2";

type ModuleKey = "report_download" | "data_analysis" | "daily_report";
type RunState = "idle" | "running" | "success" | "error";

type SkillArtifact = {
  kind: string;
  path: string;
  description?: string;
  metadata?: Record<string, unknown>;
};

type WorkflowStep = {
  name?: string;
  title?: string;
  step_id?: string;
  skill?: string;
  status?: string;
  detail?: string;
  summary?: string;
};

type SkillResult = {
  success: boolean;
  skill_name?: string;
  run_id?: string;
  runtime?: string;
  status?: string;
  spec?: Record<string, unknown>;
  summary?: string;
  artifacts?: SkillArtifact[];
  data?: Record<string, any>;
  results?: SkillResult[];
  warnings?: string[];
  error?: {
    code?: string;
    message?: string;
    recoverable?: boolean;
    details?: Record<string, unknown>;
  } | null;
  memory_updates?: Array<{
    record_id: string;
    summary?: string;
    status?: string;
  }>;
};

type ModuleConfig = {
  key: ModuleKey;
  label: string;
  shortLabel: string;
  title: string;
  summary: string;
  placeholder: string;
  buttonLabel: string;
  icon: typeof DatabaseZap;
};

const MODULES: ModuleConfig[] = [
  {
    key: "report_download",
    label: "报表下载",
    shortLabel: "下载",
    title: "FineReport 源表获取",
    summary: "自然语言解析报表类型、日期和产品型号，返回可追踪源文件。",
    placeholder: "下载 M626 近两个月的月周天良率汇总报表",
    buttonLabel: "执行下载",
    icon: DatabaseZap,
  },
  {
    key: "data_analysis",
    label: "数据分析",
    shortLabel: "分析",
    title: "Excel 数据分析",
    summary: "定位源表，抽取 schema，选择代码执行或 LLM 直读分析路径。",
    placeholder: "分析 C516 近一周 CT 良率变化趋势，并指出异常原因",
    buttonLabel: "执行分析",
    icon: BarChart3,
  },
  {
    key: "daily_report",
    label: "日报生成",
    shortLabel: "日报",
    title: "日报产物生成",
    summary: "读取 spotfire、良率、目标和异常表，输出 Excel、JSON 和 Markdown。",
    placeholder: "生成今天的良率日报，可补充产品型号或日期",
    buttonLabel: "生成日报",
    icon: FileSpreadsheet,
  },
];

const INITIAL_LOGS = [
  "Agent UI ready",
  "Python Skill bridge mounted",
  "Waiting for operator request",
];

function Suggestions() {
  useConfigureSuggestions({
    suggestions: [
      {
        title: "下载源表",
        message: "请下载 M626 近两个月的月周天良率汇总报表。",
      },
      {
        title: "分析趋势",
        message: "请分析 C516 近一周 CT 良率变化趋势。",
      },
      {
        title: "生成日报",
        message: "请生成今天的良率日报，并列出产物路径。",
      },
    ],
    available: "always",
  });

  return null;
}

export default function Page() {
  const [activeModule, setActiveModule] = useState<ModuleKey>("report_download");
  const [query, setQuery] = useState("");
  const [runState, setRunState] = useState<RunState>("idle");
  const [lastResult, setLastResult] = useState<SkillResult | null>(null);
  const [logs, setLogs] = useState<string[]>(INITIAL_LOGS);
  const [moduleStates, setModuleStates] = useState<Record<ModuleKey, RunState>>({
    report_download: "idle",
    data_analysis: "idle",
    daily_report: "idle",
  });
  const [feedbackState, setFeedbackState] = useState<RunState>("idle");

  const activeConfig = MODULES.find((module) => module.key === activeModule) || MODULES[0];
  const workflowSteps = useMemo(() => deriveWorkflowSteps(activeModule, lastResult), [
    activeModule,
    lastResult,
  ]);
  const reportRows = useMemo(() => deriveReportRows(lastResult), [lastResult]);
  const sourceCards = useMemo(() => deriveSourceCards(lastResult), [lastResult]);
  const specPreview = useMemo(() => buildSpecPreview(activeConfig, query, lastResult), [
    activeConfig,
    query,
    lastResult,
  ]);
  const pendingMemory = lastResult?.memory_updates?.[0] || null;

  async function runSkill(moduleKey: ModuleKey = activeModule, incomingQuery = query) {
    const nextQuery = incomingQuery.trim();
    if (moduleKey !== "daily_report" && !nextQuery) {
      setLastResult({
        success: false,
        skill_name: moduleKey,
        summary: "请输入需求后再执行。",
        artifacts: [],
        data: {},
        warnings: [],
        error: {
          code: "ui.input.empty",
          message: "请输入需求后再执行。",
          recoverable: true,
        },
        memory_updates: [],
      });
      setRunState("error");
      return "请输入需求后再执行。";
    }

    setActiveModule(moduleKey);
    setRunState("running");
    setModuleStates((current) => ({ ...current, [moduleKey]: "running" }));
    setLogs((current) => [
      `${moduleLabel(moduleKey)} request accepted`,
      "Creating RunContext",
      "Calling Python Skill bridge",
      ...current.slice(0, 12),
    ]);

    const moduleConfig = MODULES.find((module) => module.key === moduleKey) || activeConfig;
    const goal = nextQuery || moduleConfig.placeholder;
    const response = await fetch("/api/agent-runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "create_and_run",
        goal,
        runtime: "auto",
        options:
          moduleKey === "daily_report"
            ? { output_name: "daily_report_output.xlsx" }
            : {},
      }),
    });
    const result = normalizeAgentRunResult((await response.json()) as SkillResult);
    setLastResult(result);
    setRunState(result.success ? "success" : "error");
    setModuleStates((current) => ({
      ...current,
      [moduleKey]: result.success ? "success" : "error",
    }));
    setLogs((current) => [
      `${moduleLabel(moduleKey)} finished: ${result.success ? "success" : "failed"}`,
      result.summary || "No summary returned",
      ...deriveWorkflowSteps(moduleKey, result).map((step) => step.detail),
      ...current,
    ].slice(0, 18));
    return result.summary || "执行完成。";
  }

  async function sendMemoryFeedback(action: "confirm_memory" | "reject_memory") {
    if (!pendingMemory) {
      return;
    }
    setFeedbackState("running");
    const response = await fetch("/api/agent-runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        record_id: pendingMemory.record_id,
      }),
    });
    const result = (await response.json()) as SkillResult;
    setFeedbackState(result.success ? "success" : "error");
    setLogs((current) => [result.summary || "Memory feedback returned", ...current].slice(0, 18));
  }

  useFrontendTool({
    name: "runYieldReportSkill",
    description: "Run one yield-report workspace skill from the Agent UI.",
    parameters: z.object({
      module: z.enum(["report_download", "data_analysis", "daily_report"]),
      query: z.string().describe("Natural-language request for the selected skill."),
    }),
    handler: async ({ module, query: toolQuery }) => {
      setQuery(toolQuery);
      return runSkill(module, toolQuery);
    },
  });

  return (
    <main className="app-shell">
      <section className="workspace">
        <aside className="agent-rail" aria-label="Agent 状态">
          <div className="brand-block">
            <div className="brand-mark">
              <Brain size={20} strokeWidth={1.8} />
            </div>
            <div>
              <p className="eyebrow">Yield Agent</p>
              <h1>良率日报工作台</h1>
            </div>
          </div>

          <div className={`run-state run-state-${runState}`}>
            {runStateIcon(runState)}
            <div>
              <span>当前状态</span>
              <strong>{runStateLabel(runState)}</strong>
            </div>
          </div>

          <nav className="module-nav" aria-label="业务模块">
            {MODULES.map((module) => {
              const Icon = module.icon;
              return (
                <button
                  key={module.key}
                  className={activeModule === module.key ? "module-button active" : "module-button"}
                  onClick={() => setActiveModule(module.key)}
                  type="button"
                >
                  <Icon size={18} strokeWidth={1.8} />
                  <span>{module.label}</span>
                  <StatusDot state={moduleStates[module.key]} />
                </button>
              );
            })}
          </nav>

          <button
            className="primary-action"
            type="button"
            onClick={() => runSkill("daily_report", query)}
            disabled={runState === "running"}
          >
            {runState === "running" ? (
              <Loader2 className="spin" size={18} strokeWidth={1.8} />
            ) : (
              <Play size={18} strokeWidth={1.8} />
            )}
            <span>全自动日报</span>
          </button>
        </aside>

        <section className="main-column">
          <header className="topbar">
            <div>
              <p className="eyebrow">Spec / Skill / Runtime</p>
              <h2>{activeConfig.title}</h2>
            </div>
            <div className="health-strip">
              <span>Runtime</span>
              <strong>/api/agent-runs</strong>
            </div>
          </header>

          <section className="composer-panel">
            <div className="composer-copy">
              <p>{activeConfig.summary}</p>
              <div className="segmented-control" role="tablist" aria-label="选择模块">
                {MODULES.map((module) => (
                  <button
                    type="button"
                    key={module.key}
                    className={activeModule === module.key ? "active" : ""}
                    onClick={() => setActiveModule(module.key)}
                  >
                    {module.shortLabel}
                  </button>
                ))}
              </div>
            </div>
            <div className="composer-box">
              <textarea
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={activeConfig.placeholder}
                rows={4}
              />
              <div className="composer-actions">
                <button
                  className="ghost-action"
                  type="button"
                  onClick={() => {
                    setQuery("");
                    setLastResult(null);
                    setRunState("idle");
                    setLogs(INITIAL_LOGS);
                  }}
                >
                  <RotateCcw size={17} strokeWidth={1.8} />
                  <span>重置</span>
                </button>
                <button
                  className="send-action"
                  type="button"
                  onClick={() => runSkill()}
                  disabled={runState === "running"}
                >
                  {runState === "running" ? (
                    <Loader2 className="spin" size={17} strokeWidth={1.8} />
                  ) : (
                    <Send size={17} strokeWidth={1.8} />
                  )}
                  <span>{activeConfig.buttonLabel}</span>
                </button>
              </div>
            </div>
          </section>

          <section className="panel-grid">
            <article className="spec-panel">
              <PanelHeader icon={ClipboardList} title="TaskSpec 预览" action="draft" />
              <pre>{specPreview}</pre>
            </article>

            <article className="pipeline-panel">
              <PanelHeader icon={ShieldCheck} title="执行链路" action={runStateLabel(runState)} />
              <div className="step-list">
                {workflowSteps.map((step, index) => (
                  <div className="step-row" key={`${step.title}-${index}`}>
                    <span>{index + 1}</span>
                    <div>
                      <strong>{step.title}</strong>
                      <p>{step.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="source-grid" aria-label="数据源状态">
            {sourceCards.map((source) => (
              <article className="source-card" key={source.title}>
                <div className="source-card-header">
                  <source.icon size={18} strokeWidth={1.8} />
                  <strong>{source.title}</strong>
                </div>
                <dl>
                  <div>
                    <dt>状态</dt>
                    <dd>{source.status}</dd>
                  </div>
                  <div>
                    <dt>文件</dt>
                    <dd>{source.count}</dd>
                  </div>
                  <div>
                    <dt>最近产物</dt>
                    <dd title={source.latest}>{source.latest}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </section>
        </section>

        <aside className="result-column" aria-label="结果与日志">
          <section className="result-panel">
            <PanelHeader icon={FileSpreadsheet} title="结果" action={lastResult?.success ? "ready" : "waiting"} />
            <ResultSummary result={lastResult} />

            {pendingMemory ? (
              <div className="memory-panel">
                <strong>Memory 待确认</strong>
                <p>{pendingMemory.summary || pendingMemory.record_id}</p>
                <div>
                  <button
                    type="button"
                    onClick={() => sendMemoryFeedback("confirm_memory")}
                    disabled={feedbackState === "running"}
                  >
                    <CheckCircle2 size={16} strokeWidth={1.8} />
                    <span>确认</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => sendMemoryFeedback("reject_memory")}
                    disabled={feedbackState === "running"}
                  >
                    <XCircle size={16} strokeWidth={1.8} />
                    <span>拒绝</span>
                  </button>
                </div>
              </div>
            ) : null}

            {lastResult?.artifacts?.length ? (
              <div className="artifact-list">
                {lastResult.artifacts.map((artifact) => (
                  <a
                    key={`${artifact.kind}-${artifact.path}`}
                    href={`/api/artifact?path=${encodeURIComponent(artifact.path)}`}
                  >
                    <Download size={16} strokeWidth={1.8} />
                    <span>{artifact.kind.toUpperCase()}</span>
                  </a>
                ))}
              </div>
            ) : null}
          </section>

          <section className="preview-panel">
            <PanelHeader icon={BarChart3} title="日报预览" action={`${reportRows.length} rows`} />
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>产品</th>
                    <th>日期</th>
                    <th>目标</th>
                    <th>实际</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {reportRows.map((row) => (
                    <tr key={`${row.product}-${row.date}`}>
                      <td>{row.product}</td>
                      <td>{row.date}</td>
                      <td>{row.target}</td>
                      <td>{row.actual}</td>
                      <td>
                        <span className={row.qualified ? "status-badge ok" : "status-badge warn"}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {!reportRows.length ? (
                    <tr>
                      <td colSpan={5} className="empty-cell">
                        等待日报 Skill 返回结构化产品结果
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="logger-panel">
            <PanelHeader icon={AlertCircle} title="Agent Logger" action="live" />
            <div className="log-stream">
              {logs.map((log, index) => (
                <p key={`${log}-${index}`}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  {log}
                </p>
              ))}
            </div>
          </section>
        </aside>
      </section>

      <Suggestions />
      <CopilotSidebar
        agentId="default"
        defaultOpen={true}
        labels={{
          modalHeaderTitle: "良率日报助手",
        }}
      />
    </main>
  );
}

function PanelHeader({
  icon: Icon,
  title,
  action,
}: {
  icon: typeof DatabaseZap;
  title: string;
  action: string;
}) {
  return (
    <div className="panel-header">
      <div>
        <Icon size={17} strokeWidth={1.8} />
        <h3>{title}</h3>
      </div>
      <span>{action}</span>
    </div>
  );
}

function StatusDot({ state }: { state: RunState }) {
  return <i className={`status-dot status-dot-${state}`} aria-hidden="true" />;
}

function ResultSummary({ result }: { result: SkillResult | null }) {
  if (!result) {
    return (
      <div className="empty-result">
        <p>选择模块并提交需求后，结果会在这里汇总。</p>
      </div>
    );
  }

  return (
    <div className={result.success ? "result-summary success" : "result-summary error"}>
      <div>
        {result.success ? <CheckCircle2 size={18} strokeWidth={1.8} /> : <XCircle size={18} strokeWidth={1.8} />}
        <strong>{result.summary || "Skill returned"}</strong>
      </div>
      {result.error?.message ? <p>{result.error.message}</p> : null}
      {result.warnings?.length ? (
        <ul>
          {result.warnings.slice(0, 3).map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      <ResultDetails result={result} />
    </div>
  );
}

function ResultDetails({ result }: { result: SkillResult }) {
  const parsed = result.data?.parsed_request as Record<string, unknown> | undefined;
  const files = (result.data?.files as Array<Record<string, unknown>> | undefined) || [];
  const resultText = result.data?.result_text as string | undefined;

  if (result.skill_name === "report_download" && (parsed || files.length)) {
    return (
      <div className="details-block">
        {parsed ? (
          <dl>
            <div>
              <dt>报表类型</dt>
              <dd>{stringValue(parsed.report_type)}</dd>
            </div>
            <div>
              <dt>日期</dt>
              <dd>
                {stringValue(parsed.start_date)} ~ {stringValue(parsed.end_date)}
              </dd>
            </div>
            <div>
              <dt>产品</dt>
              <dd>{arrayValue(parsed.product_models)}</dd>
            </div>
          </dl>
        ) : null}
        {files.map((file) => (
          <p key={String(file.file_path || file.file_description)}>
            {String(file.file_description || "file")}：{String(file.file_path || file.error_message || "N/A")}
          </p>
        ))}
      </div>
    );
  }

  if (result.skill_name === "data_analysis" && resultText) {
    return <pre className="analysis-text">{resultText}</pre>;
  }

  return null;
}

function runStateIcon(state: RunState) {
  if (state === "running") {
    return <Loader2 className="spin" size={18} strokeWidth={1.8} />;
  }
  if (state === "success") {
    return <CheckCircle2 size={18} strokeWidth={1.8} />;
  }
  if (state === "error") {
    return <XCircle size={18} strokeWidth={1.8} />;
  }
  return <ShieldCheck size={18} strokeWidth={1.8} />;
}

function runStateLabel(state: RunState) {
  return {
    idle: "就绪",
    running: "运行中",
    success: "完成",
    error: "异常",
  }[state];
}

function moduleLabel(moduleKey: ModuleKey) {
  return MODULES.find((module) => module.key === moduleKey)?.label || moduleKey;
}

function normalizeAgentRunResult(result: SkillResult): SkillResult {
  const primary = result.results?.[0];
  if (!primary) {
    return result;
  }
  return {
    ...result,
    skill_name: primary.skill_name || result.skill_name,
    summary: primary.summary || result.summary,
    data: {
      ...(primary.data || {}),
      run: result.data,
      workflow_steps: result.data?.workflow_steps || primary.data?.workflow_steps,
    },
    warnings: [...(result.warnings || []), ...(primary.warnings || [])],
    error: primary.error || result.error,
  };
}

function deriveWorkflowSteps(moduleKey: ModuleKey, result: SkillResult | null) {
  const serverSteps = (result?.data?.workflow_steps as WorkflowStep[] | undefined) || [];
  if (serverSteps.length) {
    return serverSteps.map((step) => ({
      title: step.name || step.title || step.skill || step.step_id || "workflow step",
      detail: step.detail || step.summary || step.status || "N/A",
    }));
  }

  const baseSteps: Record<ModuleKey, Array<{ title: string; detail: string }>> = {
    report_download: [
      { title: "解析需求", detail: "识别报表类型、日期范围和产品型号" },
      { title: "调用下载 Skill", detail: "复用 FineReport RPA 或本地文件定位能力" },
      { title: "返回产物", detail: "写入 resources 并生成 artifact 引用" },
    ],
    data_analysis: [
      { title: "定位源表", detail: "按自然语言需求匹配 Excel 文件" },
      { title: "选择策略", detail: "在 code 与 llm_direct 分析路径间决策" },
      { title: "生成结论", detail: "输出文本、步骤和可确认 Memory" },
    ],
    daily_report: [
      { title: "读取日报源", detail: "读取 spotfire、目标、良率和异常源表" },
      { title: "结构化分析", detail: "生成 Gap、趋势和异常事实" },
      { title: "写出日报", detail: "输出 Excel、JSON 和 Markdown 产物" },
    ],
  };
  return baseSteps[moduleKey];
}

function deriveReportRows(result: SkillResult | null) {
  const rows = (result?.data?.products as any[] | undefined) || [];
  return rows.slice(0, 8).map((item) => {
    const product = item.product || item;
    const target = toPercent(product.target_yield);
    const actual = toPercent(product.actual_yield);
    const qualified = product.is_qualified === true;
    return {
      product: product.product_type || product.product || "N/A",
      date: product.report_date || result?.data?.report_date || "N/A",
      target,
      actual,
      qualified,
      status: product.is_qualified === undefined || product.is_qualified === null
        ? "待确认"
        : qualified
          ? "达标"
          : "不达标",
    };
  });
}

function deriveSourceCards(result: SkillResult | null) {
  const artifacts = result?.artifacts || [];
  const files = ((result?.data?.files as Array<Record<string, unknown>> | undefined) || []).filter(
    (file) => file.success,
  );
  const latestArtifact = artifacts[0]?.path || files[0]?.file_path || "等待执行";
  return [
    {
      title: "FineReport 管道",
      icon: DatabaseZap,
      status: result?.skill_name === "report_download" ? statusText(result.success) : "待命",
      count: String(files.length || artifacts.filter((artifact) => artifact.kind === "excel").length || 0),
      latest: basename(String(latestArtifact)),
    },
    {
      title: "Excel 分析管道",
      icon: BarChart3,
      status: result?.skill_name === "data_analysis" ? statusText(result.success) : "待命",
      count: String(artifacts.length),
      latest: basename(String(result?.data?.source_file_path || latestArtifact)),
    },
  ];
}

function buildSpecPreview(module: ModuleConfig, query: string, result: SkillResult | null) {
  const runSpec = result?.spec || result?.data?.spec;
  if (runSpec) {
    return JSON.stringify(runSpec, null, 2);
  }

  const payload = {
    status: "draft",
    user_goal: query || module.placeholder,
    workflow: [
      {
        skill: module.key,
        input: module.key === "daily_report" ? { output_name: "daily_report_output.xlsx" } : { user_query: query },
      },
    ],
    outputs: {
      trace: "specs/runs/<run_id>/trace.jsonl",
      artifacts: "specs/runs/<run_id>/outputs/",
    },
  };
  return JSON.stringify(payload, null, 2);
}

function statusText(success?: boolean) {
  if (success === true) {
    return "成功";
  }
  if (success === false) {
    return "异常";
  }
  return "待命";
}

function stringValue(value: unknown) {
  if (value === undefined || value === null || value === "") {
    return "未指定";
  }
  return String(value);
}

function arrayValue(value: unknown) {
  return Array.isArray(value) && value.length ? value.join(", ") : stringValue(value);
}

function toPercent(value: unknown) {
  if (typeof value !== "number") {
    return "N/A";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function basename(value: string) {
  const normalized = value.replaceAll("\\", "/");
  return normalized.split("/").pop() || value;
}
