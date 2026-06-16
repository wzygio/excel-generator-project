"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { z } from "zod";
import {
  AlertCircle,
  ArrowDownToLine,
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronRight,
  DatabaseZap,
  FileSpreadsheet,
  Loader2,
  Maximize2,
  MessageSquareText,
  PencilLine,
  Play,
  Plus,
  RotateCcw,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  CopilotSidebar,
  useConfigureSuggestions,
  useFrontendTool,
} from "@copilotkit/react-core/v2";

type IntentKey = "auto" | "daily_report";
type RunState = "idle" | "running" | "success" | "error";
type DebugTab = "spec" | "trace" | "memory" | "raw" | "logs";

type SkillArtifact = {
  kind?: string;
  path?: string;
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

type MemoryCandidate = {
  record_id?: string;
  summary?: string;
  status?: string;
};

type SkillResult = {
  success?: boolean;
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
  memory_updates?: MemoryCandidate[];
  spec_path?: string;
  paths?: Record<string, string>;
};

type AssistantPrompt = {
  label: string;
  prompt: string;
  icon: LucideIcon;
};

type ConversationStatus = "idle" | "running" | "completed" | "failed";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  body?: string;
  status?: "success" | "error";
  warnings?: string[];
  artifacts?: SkillArtifact[];
  createdAt: string;
};

type ConversationSession = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  latestStatus: ConversationStatus;
  messages: ChatMessage[];
  runIds: string[];
};

type ConversationSummary = Omit<ConversationSession, "messages"> & {
  messageCount: number;
  lastMessage?: string;
};

type ConversationApiResponse = {
  success?: boolean;
  summary?: string;
  conversation?: ConversationSession;
  conversations?: ConversationSummary[];
};

type MarkdownBlock =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] }
  | { type: "table"; header: string[]; rows: string[][] };

const QUICK_PROMPTS: AssistantPrompt[] = [
  {
    label: "分析良率趋势",
    prompt: "请分析C522近一周的良率变化趋势；如果有恶化，请给出恶化原因",
    icon: BarChart3,
  },
  {
    label: "下载源表",
    prompt: "请下载M626近两个月的月周天良率汇总报表",
    icon: DatabaseZap,
  },
  {
    label: "生成日报",
    prompt: "请生成今天的良率日报，并列出Excel和Markdown产物路径",
    icon: FileSpreadsheet,
  },
];

const INITIAL_LOGS = [
  "Agent Workbench ready",
  "Runtime endpoint: /api/agent-runs",
  "Waiting for an operator request",
];

const DEBUG_TABS: Array<{ key: DebugTab; label: string }> = [
  { key: "spec", label: "TaskSpec" },
  { key: "trace", label: "Trace" },
  { key: "memory", label: "Memory" },
  { key: "raw", label: "Raw JSON" },
  { key: "logs", label: "Logs" },
];

export default function AgentWorkbenchPage() {
  const [intent, setIntent] = useState<IntentKey>("auto");
  const [query, setQuery] = useState(QUICK_PROMPTS[0].prompt);
  const [runState, setRunState] = useState<RunState>("idle");
  const [lastResult, setLastResult] = useState<SkillResult | null>(null);
  const [logs, setLogs] = useState(INITIAL_LOGS);
  const [feedbackState, setFeedbackState] = useState<
    "idle" | "sending" | "confirmed" | "corrected"
  >("idle");
  const [debugTab, setDebugTab] = useState<DebugTab>("spec");
  const [activeConversation, setActiveConversation] = useState<ConversationSession | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [expandedResult, setExpandedResult] = useState<{ title: string; text: string } | null>(
    null,
  );

  useEffect(() => {
    void loadConversations();
  }, []);

  useEffect(() => {
    if (!expandedResult) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setExpandedResult(null);
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [expandedResult]);

  useConfigureSuggestions({
    instructions:
      "你是良率日报工作台助手。优先帮助用户用自然语言发起报表下载、Excel数据分析或日报生成，并把复杂执行细节收敛成清晰结果。",
    minSuggestions: 2,
    maxSuggestions: 4,
    available: "always",
  });

  useFrontendTool({
    name: "run_yield_report_agent",
    description:
      "Run the yield-report Agent Runtime for source report download, Excel analysis, or daily report generation.",
    parameters: z.object({
      goal: z.string().min(1).describe("自然语言任务目标"),
      module: z
        .enum(["auto", "report_download", "data_analysis", "daily_report"])
        .optional()
        .describe("可选模块；下载和分析都会交给 runtime:auto 判断"),
    }),
    handler: async ({ goal, module }) => {
      const nextIntent = module === "daily_report" ? "daily_report" : "auto";
      setIntent(nextIntent);
      setQuery(goal);
      const result = await runAgent(nextIntent, goal);
      return {
        state: result?.success === false ? "error" : "success",
        summary: result?.summary || "Agent task submitted.",
      };
    },
  });

  const primarySkill = useMemo(() => derivePrimarySkill(lastResult), [lastResult]);
  const workflowSteps = useMemo(() => deriveWorkflowSteps(lastResult), [lastResult]);
  const activeMessages = activeConversation?.messages ?? [];
  const conversationArtifacts = useMemo(
    () => deriveArtifactsFromMessages(activeMessages),
    [activeMessages],
  );
  const artifacts = useMemo(() => {
    const latestArtifacts = deriveArtifacts(lastResult);
    return latestArtifacts.length ? latestArtifacts : conversationArtifacts;
  }, [lastResult, conversationArtifacts]);
  const resultText = useMemo(() => deriveResultText(lastResult), [lastResult]);
  const displaySummary = useMemo(
    () => deriveDisplaySummary(lastResult, resultText, runState),
    [lastResult, resultText, runState],
  );
  const specPreview = useMemo(() => buildSpecPreview(lastResult), [lastResult]);
  const memoryCandidate = useMemo(() => firstMemoryCandidate(lastResult), [lastResult]);
  const isRunning = runState === "running";
  const latestAssistantMessageId = useMemo(() => {
    return [...activeMessages].reverse().find((message) => message.role === "assistant")?.id;
  }, [activeMessages]);
  const activeRunId = activeConversation?.runIds.at(-1) || lastResult?.run_id || "待提交";

  async function loadConversations() {
    setIsLoadingConversations(true);
    try {
      const response = await fetch("/api/conversations", { cache: "no-store" });
      const body = (await response.json()) as ConversationApiResponse;
      if (!response.ok || body.success === false) {
        throw new Error(body.summary || "加载会话失败");
      }
      setConversations(body.conversations || []);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLogs((previous) =>
        [`${new Date().toLocaleTimeString()} conversations failed: ${message}`, ...previous].slice(
          0,
          8,
        ),
      );
    } finally {
      setIsLoadingConversations(false);
    }
  }

  async function persistConversation(conversation: ConversationSession) {
    const response = await fetch(`/api/conversations/${conversation.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation }),
    });
    const body = (await response.json()) as ConversationApiResponse;
    if (!response.ok || body.success === false || !body.conversation) {
      throw new Error(body.summary || "保存会话失败");
    }
    setActiveConversation(body.conversation);
    if (body.conversations) {
      setConversations(body.conversations);
    }
    return body.conversation;
  }

  async function selectConversation(conversationId: string) {
    if (isRunning) return;
    setIsLoadingConversations(true);
    try {
      const response = await fetch(`/api/conversations/${conversationId}`, { cache: "no-store" });
      const body = (await response.json()) as ConversationApiResponse;
      if (!response.ok || body.success === false || !body.conversation) {
        throw new Error(body.summary || "读取会话失败");
      }
      const restored = body.conversation;
      const latestUser = [...restored.messages]
        .reverse()
        .find((message) => message.role === "user");
      setActiveConversation(restored);
      setLastResult(null);
      setRunState(statusToRunState(restored.latestStatus));
      setFeedbackState("idle");
      setDebugTab("spec");
      setQuery(latestUser?.content || QUICK_PROMPTS[0].prompt);
      setLogs((previous) =>
        [
          `${new Date().toLocaleTimeString()} restored conversation: ${restored.title}`,
          ...previous,
        ].slice(0, 8),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLogs((previous) =>
        [`${new Date().toLocaleTimeString()} restore failed: ${message}`, ...previous].slice(0, 8),
      );
    } finally {
      setIsLoadingConversations(false);
    }
  }

  function startNewConversation() {
    if (isRunning) return;
    setIntent("auto");
    setQuery(QUICK_PROMPTS[0].prompt);
    setRunState("idle");
    setLastResult(null);
    setActiveConversation(null);
    setFeedbackState("idle");
    setDebugTab("spec");
  }

  async function runAgent(
    nextIntent: IntentKey = intent,
    incomingGoal?: string,
  ): Promise<SkillResult | null> {
    const goal = (incomingGoal ?? query).trim();
    if (!goal || runState === "running") {
      return null;
    }

    let activeRunConversation: ConversationSession | null = null;
    setIntent(nextIntent);
    setRunState("running");
    setLastResult(null);
    setFeedbackState("idle");
    setLogs((previous) =>
      [`${new Date().toLocaleTimeString()} submitted: ${goal}`, ...previous].slice(0, 8),
    );

    try {
      const now = new Date().toISOString();
      const baseConversation = activeConversation || createLocalConversation(goal, now);
      const userMessage = createUserMessage(goal, now);
      activeRunConversation = {
        ...baseConversation,
        title: baseConversation.messages.length ? baseConversation.title : titleFromGoal(goal),
        latestStatus: "running",
        updatedAt: now,
        messages: [...baseConversation.messages, userMessage],
      };
      setActiveConversation(activeRunConversation);
      void persistConversation(activeRunConversation).catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        setLogs((previous) =>
          [`${new Date().toLocaleTimeString()} conversation save failed: ${message}`, ...previous].slice(
            0,
            8,
          ),
        );
      });

      const response = await fetch("/api/agent-runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "create_and_run",
          goal,
          runtime: "auto",
          options:
            nextIntent === "daily_report"
              ? { output_name: "daily_report_output.xlsx" }
              : { prefer_existing_tools: true },
        }),
      });

      const body = (await response.json()) as SkillResult;
      if (!response.ok || body.success === false) {
        const failedAt = new Date().toISOString();
        const failedResult: SkillResult = {
          ...body,
          success: false,
          status: body.status || "failed",
          summary: body.summary || body.error?.message || "Agent runtime failed",
        };
        const failedBody =
          deriveResultText(failedResult) ||
          failedResult.error?.message ||
          failedResult.summary ||
          "Agent runtime failed";
        const failedConversation: ConversationSession = {
          ...activeRunConversation,
          latestStatus: "failed",
          updatedAt: failedAt,
          runIds: Array.from(
            new Set(
              [...activeRunConversation.runIds, failedResult.run_id].filter(
                (runId): runId is string => Boolean(runId),
              ),
            ),
          ),
          messages: [
            ...activeRunConversation.messages,
            createAssistantMessage({
              result: failedResult,
              runState: "error",
              body: failedBody,
              createdAt: failedAt,
            }),
          ],
        };
        setActiveConversation(failedConversation);
        setLastResult(failedResult);
        setRunState("error");
        await persistConversation(failedConversation);
        setLogs((previous) =>
          [
            `${new Date().toLocaleTimeString()} blocked: ${
              failedResult.error?.message || failedResult.summary
            }`,
            ...previous,
          ].slice(0, 8),
        );
        return failedResult;
      }

      const outputText = deriveResultText(body);
      const completedAt = new Date().toISOString();
      const assistantMessage = createAssistantMessage({
        result: body,
        runState: "success",
        body: outputText,
        createdAt: completedAt,
      });
      const completedConversation: ConversationSession = {
        ...activeRunConversation,
        latestStatus: "completed",
        updatedAt: completedAt,
        runIds: Array.from(
          new Set(
            [...activeRunConversation.runIds, body.run_id].filter(
              (runId): runId is string => Boolean(runId),
            ),
          ),
        ),
        messages: [...activeRunConversation.messages, assistantMessage],
      };
      setLastResult(body);
      setRunState("success");
      await persistConversation(completedConversation);
      setLogs((previous) =>
        [
          `${new Date().toLocaleTimeString()} completed: ${skillLabel(
            derivePrimarySkill(body),
          )}`,
          ...previous,
        ].slice(0, 8),
      );
      return body;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const errorResult: SkillResult = {
        success: false,
        status: "failed",
        summary: message,
        error: {
          code: "ui.agent_run_failed",
          message,
          recoverable: true,
        },
      };
      if (activeRunConversation) {
        const failedAt = new Date().toISOString();
        const failedConversation: ConversationSession = {
          ...activeRunConversation,
          latestStatus: "failed",
          updatedAt: failedAt,
          messages: [
            ...activeRunConversation.messages,
            createAssistantMessage({
              result: errorResult,
              runState: "error",
              body: message,
              createdAt: failedAt,
            }),
          ],
        };
        setActiveConversation(failedConversation);
        void persistConversation(failedConversation).catch((saveError) => {
          const saveMessage = saveError instanceof Error ? saveError.message : String(saveError);
          setLogs((previous) =>
            [
              `${new Date().toLocaleTimeString()} conversation save failed: ${saveMessage}`,
              ...previous,
            ].slice(0, 8),
          );
        });
      }
      setLastResult(errorResult);
      setRunState("error");
      setLogs((previous) =>
        [`${new Date().toLocaleTimeString()} failed: ${message}`, ...previous].slice(0, 8),
      );
      return errorResult;
    }
  }

  function submitPrompt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runAgent(intent);
  }

  function runFixedDailyReport() {
    const goal =
      intent === "daily_report" && query.trim()
        ? query.trim()
        : "请生成今天的良率日报，并列出Excel和Markdown产物路径";
    setQuery(goal);
    void runAgent("daily_report", goal);
  }

  function resetWorkspace() {
    startNewConversation();
    setLogs(INITIAL_LOGS);
  }

  async function sendMemoryFeedback(action: "confirm" | "correct", correction = "") {
    const recordId = memoryCandidate?.record_id;
    if (!recordId || feedbackState === "sending" || runState === "running") {
      return;
    }
    const trimmedCorrection = correction.trim();
    if (action === "correct" && !trimmedCorrection) {
      return;
    }
    setFeedbackState("sending");
    try {
      const response = await fetch("/api/agent-runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: action === "confirm" ? "confirm_memory" : "correct_memory",
          record_id: recordId,
          correction: trimmedCorrection,
        }),
      });
      const body = (await response.json()) as SkillResult;
      if (!response.ok || body.success === false) {
        throw new Error(body.error?.message || body.summary || "Memory feedback failed");
      }
      setFeedbackState(action === "confirm" ? "confirmed" : "corrected");
      setLogs((previous) =>
        [
          `${new Date().toLocaleTimeString()} memory ${action}: ${recordId}`,
          ...previous,
        ].slice(0, 8),
      );
      if (action === "correct") {
        const baseGoal = latestUserGoal(activeConversation) || query;
        const correctedGoal = `${baseGoal}\n\n用户修正：${trimmedCorrection}`;
        setQuery(correctedGoal);
        await runAgent(intent, correctedGoal);
      }
    } catch (error) {
      setFeedbackState("idle");
      const message = error instanceof Error ? error.message : String(error);
      setLogs((previous) =>
        [`${new Date().toLocaleTimeString()} memory feedback failed: ${message}`, ...previous].slice(
          0,
          8,
        ),
      );
    }
  }

  return (
    <main className="agent-workbench">
      <section className="workbench-grid" aria-label="良率日报 Agent 工作台">
        <aside className="rail">
          <div className="brand">
            <div className="brand-mark">
              <Bot size={22} aria-hidden />
            </div>
            <div>
              <p className="eyebrow">Yield Agent</p>
              <h1>良率日报工作台</h1>
            </div>
          </div>

          <div className="runtime-card">
            <div className="status-line">
              {stateIcon(runState)}
              <span>{stateLabel(runState)}</span>
            </div>
            <p>Runtime 统一接管报表下载、数据分析与日报生成。</p>
          </div>

          <nav className="intent-nav" aria-label="任务入口">
            <button
              className={intent === "auto" ? "nav-item active" : "nav-item"}
              type="button"
              onClick={() => setIntent("auto")}
            >
              <Sparkles size={17} aria-hidden />
              <span>智能任务</span>
              <small>下载 / 分析</small>
            </button>
            <button
              className={intent === "daily_report" ? "nav-item active" : "nav-item"}
              type="button"
              onClick={() => setIntent("daily_report")}
            >
              <FileSpreadsheet size={17} aria-hidden />
              <span>固定日报</span>
              <small>标准产物</small>
            </button>
          </nav>

          <div className="rail-note">
            <p>调试信息已折叠到主区域下方，可随时查看 TaskSpec、Trace 与 Memory。</p>
          </div>

          <button className="daily-button" type="button" onClick={runFixedDailyReport}>
            <Play size={17} aria-hidden />
            生成日报
          </button>
        </aside>

        <section className="conversation-area">
          <header className="workbench-header">
            <div>
              <p className="eyebrow">Spec / Skill / Runtime</p>
              <h2>Agent 对话工作区</h2>
            </div>
            <div className="header-metrics">
              <Metric label="入口" value={intent === "daily_report" ? "固定日报" : "智能任务"} />
              <Metric label="Skill" value={skillLabel(primarySkill)} />
              <Metric label="Run" value={activeRunId} />
            </div>
          </header>

          <div className="chat-surface" aria-live="polite">
            <div className="message-row assistant">
              <div className="avatar">
                <Bot size={18} aria-hidden />
              </div>
              <div className="message-card">
                <p className="message-kicker">Agent</p>
                <p>
                  直接描述你要下载的报表、要分析的 Excel 问题，或要生成的日报。Runtime 会创建
                  TaskSpec 并选择合适 skill 执行。
                </p>
              </div>
            </div>

            {activeMessages.map((message) =>
              message.role === "user" ? (
                <div className="message-row user" key={message.id}>
                  <div className="message-card user-card">
                    <p className="message-kicker">你</p>
                    <p>{message.content}</p>
                  </div>
                </div>
              ) : (
                <div className="message-row assistant" key={message.id}>
                  <div className={message.status === "error" ? "avatar error" : "avatar success"}>
                    {stateIcon(message.status === "error" ? "error" : "success")}
                  </div>
                  <div className="message-card result-message">
                    <p className="message-kicker">{message.status === "error" ? "失败" : "结果"}</p>
                    <p>{message.content}</p>
                    {message.body ? (
                      <button
                        className="expand-result-button"
                        type="button"
                        onClick={() =>
                          setExpandedResult({
                            title: message.content,
                            text: message.body || message.content,
                          })
                        }
                      >
                        <Maximize2 size={15} aria-hidden />
                        放大
                      </button>
                    ) : null}
                    {message.body && message.body !== message.content ? (
                      <ResultBody text={message.body} />
                    ) : null}
                    {message.warnings?.length ? (
                      <div className="warning-strip">
                        <AlertCircle size={16} aria-hidden />
                        <span>{message.warnings.join("；")}</span>
                      </div>
                    ) : null}
                    {message.id === latestAssistantMessageId && memoryCandidate ? (
                      <MemoryFeedback
                        candidate={memoryCandidate}
                        feedbackState={feedbackState}
                        onFeedback={sendMemoryFeedback}
                      />
                    ) : null}
                  </div>
                </div>
              ),
            )}

            {isRunning ? (
              <div className="message-row assistant">
                <div className="avatar running">
                  <Loader2 size={18} aria-hidden />
                </div>
                <div className="message-card run-card">
                  <p className="message-kicker">执行中</p>
                  <p>正在生成 TaskSpec、路由 Skill，并汇总结果。复杂 Excel 分析可能需要一些时间。</p>
                </div>
              </div>
            ) : null}

            {lastResult && runState !== "running" && !activeMessages.length ? (
              <div className="message-row assistant">
                <div className={runState === "error" ? "avatar error" : "avatar success"}>
                  {stateIcon(runState)}
                </div>
                <div className="message-card result-message">
                  <p className="message-kicker">{runState === "error" ? "失败" : "结果"}</p>
                  <p>{displaySummary}</p>
                  {resultText ? (
                    <button
                      className="expand-result-button"
                      type="button"
                      onClick={() => setExpandedResult({ title: displaySummary, text: resultText })}
                    >
                      <Maximize2 size={15} aria-hidden />
                      放大
                    </button>
                  ) : null}
                  {resultText ? <ResultBody text={resultText} /> : null}
                  {lastResult.warnings?.length ? (
                    <div className="warning-strip">
                      <AlertCircle size={16} aria-hidden />
                      <span>{lastResult.warnings.join("；")}</span>
                    </div>
                  ) : null}
                  {memoryCandidate ? (
                    <MemoryFeedback
                      candidate={memoryCandidate}
                      feedbackState={feedbackState}
                      onFeedback={sendMemoryFeedback}
                    />
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>

          <form className="prompt-dock" onSubmit={submitPrompt}>
            <div className="prompt-tabs" role="tablist" aria-label="任务模式">
              <button
                type="button"
                className={intent === "auto" ? "active" : ""}
                onClick={() => setIntent("auto")}
              >
                <Sparkles size={15} aria-hidden />
                智能判断
              </button>
              <button
                type="button"
                className={intent === "daily_report" ? "active" : ""}
                onClick={() => setIntent("daily_report")}
              >
                <FileSpreadsheet size={15} aria-hidden />
                固定日报
              </button>
            </div>

            <textarea
              id="agent-goal"
              name="agent-goal"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="例如：请分析C522近一周的良率变化趋势；如果有恶化，请给出恶化原因"
              rows={4}
            />

            <div className="prompt-footer">
              <div className="prompt-chips" aria-label="常用任务">
                {QUICK_PROMPTS.map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => {
                      setQuery(item.prompt);
                      setIntent(item.label === "生成日报" ? "daily_report" : "auto");
                    }}
                  >
                    <item.icon size={15} aria-hidden />
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="prompt-actions">
                <button className="ghost-button" type="button" onClick={resetWorkspace}>
                  <RotateCcw size={16} aria-hidden />
                  重置
                </button>
                <button className="primary-button" type="submit" disabled={!query.trim() || isRunning}>
                  {isRunning ? <Loader2 size={17} aria-hidden /> : <Send size={17} aria-hidden />}
                  执行
                </button>
              </div>
            </div>
          </form>

          <details className="debug-drawer">
            <summary>
              <span>
                <Settings2 size={17} aria-hidden />
                调试信息
              </span>
              <ChevronRight size={17} aria-hidden />
            </summary>
            <div className="debug-tabs" role="tablist" aria-label="调试信息">
              {DEBUG_TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  className={debugTab === tab.key ? "active" : ""}
                  onClick={() => setDebugTab(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <pre className="debug-output">{debugContent(debugTab, lastResult, logs, specPreview)}</pre>
          </details>
        </section>

        <aside className="result-area">
          <section className="result-panel history-panel">
            <PanelHeader
              icon={MessageSquareText}
              title="历史会话"
              badge={isLoadingConversations ? "loading" : `${conversations.length} chats`}
            />
            <div className="history-toolbar">
              <button type="button" onClick={startNewConversation} disabled={isRunning}>
                <Plus size={15} aria-hidden />
                新对话
              </button>
            </div>
            {conversations.length ? (
              <div className="history-list">
                {conversations.map((item) => (
                  <button
                    className={`history-item ${item.latestStatus} ${
                      activeConversation?.id === item.id ? "active" : ""
                    }`}
                    key={item.id}
                    type="button"
                    onClick={() => void selectConversation(item.id)}
                    disabled={isRunning}
                  >
                    <div className="history-head">
                      <span>{formatDateTime(item.updatedAt)}</span>
                      <strong>{conversationStatusLabel(item.latestStatus)}</strong>
                    </div>
                    <p>{item.title}</p>
                    <small>{item.lastMessage || "暂无消息"}</small>
                    <div className="history-meta">
                      <span>{item.messageCount} 条消息</span>
                      <span>{item.runIds.length} 次执行</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="empty-note">暂无历史会话。提交一次任务后，可从这里恢复并继续对话。</p>
            )}
          </section>

          <section className="result-panel artifact-panel">
            <PanelHeader icon={ArrowDownToLine} title="当前产物" badge={`${artifacts.length} files`} />
            {artifacts.length ? (
              <div className="artifact-list current-artifacts">
                {artifacts.map((artifact, index) => (
                  <div className="artifact-item" key={`${artifact.path}-${index}`}>
                    <ArrowDownToLine size={16} aria-hidden />
                    <div>
                      <strong>{artifactLabel(artifact)}</strong>
                      <span>{artifact.path}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-note">运行后会列出 Excel、Markdown 或 JSON 产物路径。</p>
            )}
          </section>
        </aside>
      </section>

      {expandedResult ? (
        <div className="result-modal-backdrop" role="presentation">
          <section className="result-modal" role="dialog" aria-modal="true" aria-label="放大分析结果">
            <header>
              <div>
                <p className="eyebrow">Analysis Result</p>
                <h2>{expandedResult.title}</h2>
              </div>
              <button
                type="button"
                aria-label="关闭放大结果"
                onClick={() => setExpandedResult(null)}
              >
                <X size={18} aria-hidden />
              </button>
            </header>
            <div className="result-modal-body">
              <ResultBody text={expandedResult.text} />
            </div>
          </section>
        </div>
      ) : null}

      <CopilotSidebar
        defaultOpen={false}
        labels={{
          chatInputPlaceholder: "下载报表、分析 Excel 或生成日报…",
          welcomeMessageText: "你可以让我下载报表、分析 Excel 或生成日报。",
        }}
      />
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong title={value}>{value}</strong>
    </div>
  );
}

function PanelHeader({
  icon: Icon,
  title,
  badge,
}: {
  icon: LucideIcon;
  title: string;
  badge?: string;
}) {
  return (
    <div className="panel-header">
      <div>
        <Icon size={17} aria-hidden />
        <h3>{title}</h3>
      </div>
      {badge ? <span>{badge}</span> : null}
    </div>
  );
}

function MemoryFeedback({
  candidate,
  feedbackState,
  onFeedback,
}: {
  candidate: MemoryCandidate;
  feedbackState: "idle" | "sending" | "confirmed" | "corrected";
  onFeedback: (action: "confirm" | "correct", correction?: string) => void;
}) {
  const [isCorrecting, setIsCorrecting] = useState(false);
  const [correction, setCorrection] = useState("");
  const canSubmitCorrection = correction.trim().length > 0 && feedbackState !== "sending";

  return (
    <div className="memory-inline">
      <ShieldCheck size={16} aria-hidden />
      <div>
        <strong>Memory 待确认</strong>
        <span>{candidate.summary || `待确认数据分析记忆: ${candidate.record_id}`}</span>
      </div>
      <div className="memory-actions">
        <button
          type="button"
          onClick={() => onFeedback("confirm")}
          disabled={feedbackState === "sending"}
        >
          <CheckCircle2 size={16} aria-hidden />
          确认
        </button>
        <button
          type="button"
          onClick={() => setIsCorrecting((value) => !value)}
          disabled={feedbackState === "sending"}
        >
          <PencilLine size={16} aria-hidden />
          修正
        </button>
      </div>
      {isCorrecting ? (
        <form
          className="memory-correction"
          onSubmit={(event) => {
            event.preventDefault();
            onFeedback("correct", correction);
          }}
        >
          <textarea
            value={correction}
            onChange={(event) => setCorrection(event.target.value)}
            placeholder="说明正确工作流，例如：源表已过期，应重新下载；月数筛选改为3；先做 Table Schema Detect 再分析。"
            rows={3}
          />
          <button type="submit" disabled={!canSubmitCorrection}>
            <Send size={15} aria-hidden />
            提交修正
          </button>
        </form>
      ) : null}
    </div>
  );
}

function ResultBody({ text }: { text: string }) {
  const blocks = useMemo(() => parseMarkdownLite(text), [text]);

  return (
    <div className="analysis-output">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return <h4 key={`${block.type}-${index}`}>{block.text}</h4>;
        }
        if (block.type === "list") {
          return (
            <ul key={`${block.type}-${index}`}>
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>{item}</li>
              ))}
            </ul>
          );
        }
        if (block.type === "table") {
          return (
            <div className="markdown-table-wrap" key={`${block.type}-${index}`}>
              <table>
                <thead>
                  <tr>
                    {block.header.map((cell, cellIndex) => (
                      <th key={`${cell}-${cellIndex}`}>{cell}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={`${row.join("-")}-${rowIndex}`}>
                      {row.map((cell, cellIndex) => (
                        <td key={`${cell}-${cellIndex}`}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={`${block.type}-${index}`}>{block.text}</p>;
      })}
    </div>
  );
}

function RunTimeline({ state, steps }: { state: RunState; steps: WorkflowStep[] }) {
  const fallback: WorkflowStep[] = [
    {
      name: "创建 TaskSpec",
      status: state === "idle" ? "pending" : "done",
      detail: "解析自然语言目标",
    },
    {
      name: "选择 Skill",
      status: state === "running" ? "running" : state === "idle" ? "pending" : "done",
      detail: "由 Runtime 自动路由",
    },
    {
      name: "汇总结果",
      status: state === "success" ? "done" : state === "error" ? "failed" : "pending",
      detail: "输出结论与产物",
    },
  ];
  const rendered = steps.length ? steps : fallback;

  return (
    <div className="timeline-grid">
      {rendered.slice(0, 4).map((step, index) => {
        const status = normalizeStepStatus(step.status, state, index, rendered.length);
        return (
          <div className={`timeline-step ${status}`} key={`${step.name}-${index}`}>
            <span>{index + 1}</span>
            <div>
              <strong>{step.title || step.name || step.skill || `Step ${index + 1}`}</strong>
              <p>{cleanStepDetail(step.detail || step.summary || status)}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function stateIcon(state: RunState) {
  if (state === "running") {
    return <Loader2 size={18} aria-hidden />;
  }
  if (state === "success") {
    return <CheckCircle2 size={18} aria-hidden />;
  }
  if (state === "error") {
    return <XCircle size={18} aria-hidden />;
  }
  return <ShieldCheck size={18} aria-hidden />;
}

function stateLabel(state: RunState) {
  if (state === "running") return "执行中";
  if (state === "success") return "完成";
  if (state === "error") return "失败";
  return "待命";
}

function createLocalConversation(goal: string, now: string): ConversationSession {
  return {
    id: createId(),
    title: titleFromGoal(goal),
    createdAt: now,
    updatedAt: now,
    latestStatus: "idle",
    messages: [],
    runIds: [],
  };
}

function createUserMessage(content: string, createdAt: string): ChatMessage {
  return {
    id: createId(),
    role: "user",
    content,
    createdAt,
  };
}

function createAssistantMessage({
  result,
  runState,
  body,
  createdAt,
}: {
  result: SkillResult;
  runState: "success" | "error";
  body: string;
  createdAt: string;
}): ChatMessage {
  return {
    id: createId(),
    role: "assistant",
    content: deriveDisplaySummary(result, body, runState),
    body,
    status: runState,
    warnings: result.warnings || [],
    artifacts: deriveArtifacts(result),
    createdAt,
  };
}

function createId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function titleFromGoal(goal: string) {
  const normalized = goal.replace(/\s+/g, " ").trim();
  if (!normalized) return "新会话";
  return normalized.length > 34 ? `${normalized.slice(0, 34)}...` : normalized;
}

function statusToRunState(status: ConversationStatus): RunState {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  return "idle";
}

function latestUserGoal(conversation: ConversationSession | null) {
  return (
    [...(conversation?.messages || [])].reverse().find((message) => message.role === "user")
      ?.content || ""
  );
}

function conversationStatusLabel(status: ConversationStatus) {
  if (status === "completed") return "完成";
  if (status === "failed") return "失败";
  if (status === "running") return "执行中";
  return "草稿";
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalizeStepStatus(
  status: string | undefined,
  runState: RunState,
  index: number,
  length: number,
) {
  const lowered = String(status || "").toLowerCase();
  if (lowered.includes("fail") || lowered.includes("error")) return "failed";
  if (lowered.includes("run") || lowered.includes("progress")) return "running";
  if (lowered.includes("success") || lowered.includes("succeed") || lowered.includes("done")) {
    return "done";
  }
  if (runState === "success") return "done";
  if (runState === "error" && index === length - 1) return "failed";
  if (runState === "running" && index === 1) return "running";
  return "pending";
}

function derivePrimarySkill(result: SkillResult | null) {
  if (!result) return undefined;
  if (result.skill_name) return result.skill_name;
  const nested = result.results?.find((item) => item.skill_name)?.skill_name;
  if (nested) return nested;
  const dataResults = result.data?.results as SkillResult[] | undefined;
  return dataResults?.find((item) => item.skill_name)?.skill_name;
}

function skillLabel(skillName?: string) {
  if (!skillName) return "Runtime 自动";
  if (skillName.includes("daily")) return "日报生成";
  if (skillName.includes("download") || skillName.includes("finereport")) return "报表下载";
  if (skillName.includes("analysis")) return "数据分析";
  return skillName;
}

function deriveWorkflowSteps(result: SkillResult | null): WorkflowStep[] {
  if (!result) return [];
  const nestedResults = result.results || (result.data?.results as SkillResult[] | undefined) || [];
  const nestedSteps = nestedResults.flatMap((item) =>
    Array.isArray(item.data?.workflow_steps) ? (item.data.workflow_steps as WorkflowStep[]) : [],
  );
  if (nestedSteps.length) {
    return nestedSteps.map((step) => ({
      ...step,
      detail: cleanStepDetail(step.detail || step.summary || step.status || ""),
    }));
  }
  const fromData = result.data?.workflow_steps;
  if (Array.isArray(fromData)) {
    return (fromData as WorkflowStep[]).map((step) => ({
      ...step,
      detail: cleanStepDetail(step.detail || step.summary || step.status || ""),
    }));
  }
  if (Array.isArray(nestedResults)) {
    return nestedResults.map((item) => ({
      name: skillLabel(item.skill_name),
      status: item.success === false ? "failed" : "succeeded",
      detail: cleanStepDetail(item.summary || ""),
    }));
  }
  return [];
}

function deriveResultText(result: SkillResult | null) {
  if (!result) return "";
  const nestedResults = result.results || (result.data?.results as SkillResult[] | undefined) || [];
  const textCandidates = nestedResults
    .map(
      (item) =>
        item.data?.result_text ||
        item.data?.result ||
        item.data?.markdown ||
        item.data?.analysis ||
        item.summary,
    )
    .filter(Boolean);
  const direct =
    result.data?.result_text || result.data?.result || result.data?.markdown || result.data?.analysis;
  const chosen = direct || textCandidates[0] || "";
  return typeof chosen === "string" ? chosen : JSON.stringify(chosen, null, 2);
}

function deriveDisplaySummary(result: SkillResult | null, resultText: string, runState: RunState) {
  if (!result) {
    if (runState === "running") return "正在生成 TaskSpec 并执行 Runtime。";
    return "等待任务提交";
  }
  if (result.success === false || runState === "error") {
    return result.error?.message || result.summary || "Agent 执行失败。";
  }
  const skill = skillLabel(derivePrimarySkill(result));
  const artifactCount = deriveArtifacts(result).length;
  if (resultText) {
    if (skill === "数据分析") return `分析完成，已生成趋势结论和 ${artifactCount} 个产物。`;
    if (skill === "日报生成") return `日报生成完成，已输出 ${artifactCount} 个产物。`;
    if (skill === "报表下载") return `报表下载完成，已记录 ${artifactCount} 个文件。`;
  }
  return result.summary ? summarizeRuntimeSummary(result.summary) : "Agent 已完成执行。";
}

function parseMarkdownLite(markdown: string): MarkdownBlock[] {
  const lines = markdown.split(/\r?\n/);
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    if (line.startsWith("|") && isMarkdownTableSeparator(lines[index + 1])) {
      const tableLines: string[] = [line];
      index += 2;
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        tableLines.push(lines[index].trim());
        index += 1;
      }
      const [header, ...rows] = tableLines.map(parseMarkdownTableRow);
      blocks.push({ type: "table", header, rows });
      continue;
    }

    if (/^#{2,4}\s+/.test(line)) {
      blocks.push({ type: "heading", text: stripInlineMarkdown(line.replace(/^#{2,4}\s+/, "")) });
      index += 1;
      continue;
    }

    if (line.startsWith("- ")) {
      const items: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith("- ")) {
        items.push(stripInlineMarkdown(lines[index].trim().replace(/^-\s+/, "")));
        index += 1;
      }
      blocks.push({ type: "list", items });
      continue;
    }

    blocks.push({ type: "paragraph", text: stripInlineMarkdown(line) });
    index += 1;
  }

  return blocks;
}

function isMarkdownTableSeparator(line?: string) {
  return Boolean(line?.trim().match(/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/));
}

function parseMarkdownTableRow(line: string) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => stripInlineMarkdown(cell.trim().replace(/^---:?$/, "")));
}

function stripInlineMarkdown(text: string) {
  return text.replace(/`([^`]+)`/g, "$1").replace(/\*\*([^*]+)\*\*/g, "$1");
}

function summarizeRuntimeSummary(summary: string) {
  const firstLine = summary
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line && !line.startsWith("策略") && !line.startsWith("判定理由"));
  if (!firstLine) return "Agent 已完成执行。";
  return firstLine.replace(/^✅\s*/, "");
}

function cleanStepDetail(detail: string) {
  const normalized = detail.replace(/\s+/g, " ").trim();
  if (!normalized) return "已记录";
  if (normalized.includes("strategy=") || normalized.includes("判定理由")) {
    return "已完成策略选择，详细判定保留在调试信息中。";
  }
  if (normalized.length > 96) return `${normalized.slice(0, 96)}...`;
  return normalized;
}

function deriveArtifacts(result: SkillResult | null): SkillArtifact[] {
  if (!result) return [];
  const artifacts: SkillArtifact[] = [];
  if (Array.isArray(result.artifacts)) artifacts.push(...result.artifacts);
  const nestedResults = result.results || (result.data?.results as SkillResult[] | undefined) || [];
  for (const nested of nestedResults) {
    if (Array.isArray(nested.artifacts)) artifacts.push(...nested.artifacts);
  }
  return dedupeArtifacts(artifacts);
}

function deriveArtifactsFromMessages(messages: ChatMessage[]): SkillArtifact[] {
  const artifacts = messages.flatMap((message) => message.artifacts || []);
  return dedupeArtifacts(artifacts);
}

function dedupeArtifacts(artifacts: SkillArtifact[]) {
  const seen = new Set<string>();
  return artifacts.filter((artifact) => {
    const key = `${artifact.kind || "file"}:${artifact.path || ""}`;
    if (!artifact.path || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function artifactLabel(artifact: SkillArtifact) {
  if (artifact.description) return artifact.description;
  if (artifact.kind) return artifact.kind.toUpperCase();
  return basename(artifact.path || "artifact");
}

function deriveReportRows(result: SkillResult | null) {
  const rows =
    result?.data?.report_rows ||
    result?.data?.rows ||
    result?.data?.preview_rows ||
    result?.results?.find((item) => item.data?.report_rows)?.data?.report_rows ||
    [];
  if (!Array.isArray(rows)) return [];
  return rows.map((row: Record<string, any>) => ({
    product: String(row.product || row.model || row.product_model || "-"),
    date: String(row.date || row.report_date || "-"),
    target: Number(row.target ?? row.target_yield ?? 0),
    actual: Number(row.actual ?? row.actual_yield ?? row.yield ?? 0),
  }));
}

function buildSpecPreview(result: SkillResult | null) {
  const spec = result?.spec || result?.data?.spec || result?.data?.task_spec;
  if (!spec) return "TaskSpec 尚未生成。";
  return JSON.stringify(spec, null, 2);
}

function firstMemoryCandidate(result: SkillResult | null): MemoryCandidate | undefined {
  const updates = result?.memory_updates || [];
  const dataCandidates = result?.data?.memory_candidates;
  if (Array.isArray(dataCandidates) && dataCandidates.length) {
    return dataCandidates[0] as MemoryCandidate;
  }
  return updates[0];
}

function debugContent(
  tab: DebugTab,
  result: SkillResult | null,
  logs: string[],
  specPreview: string,
) {
  if (tab === "logs") return logs.join("\n");
  if (!result) return tab === "spec" ? specPreview : "暂无运行数据。";
  if (tab === "spec") return specPreview;
  if (tab === "trace") return JSON.stringify(result.data?.trace || [], null, 2);
  if (tab === "memory") {
    return JSON.stringify(
      {
        candidates: result.data?.memory_candidates || [],
        updates: result.memory_updates || [],
      },
      null,
      2,
    );
  }
  return JSON.stringify(result, null, 2);
}

function toPercent(value: number) {
  if (!Number.isFinite(value)) return "-";
  const normalized = value > 1 ? value : value * 100;
  return `${normalized.toFixed(2)}%`;
}

function basename(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() || path;
}
