import { randomUUID } from "crypto";
import { mkdir, readFile, readdir, writeFile } from "fs/promises";
import path from "path";

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  body?: string;
  status?: "success" | "error";
  warnings?: string[];
  artifacts?: Array<Record<string, unknown>>;
  createdAt: string;
};

export type ConversationRecord = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  latestStatus: "idle" | "running" | "completed" | "failed";
  messages: ConversationMessage[];
  runIds: string[];
};

export type ConversationSummary = Omit<ConversationRecord, "messages"> & {
  messageCount: number;
  lastMessage?: string;
};

export function workspaceRoot() {
  return process.env.YIELD_REPORT_WORKSPACE
    ? path.resolve(process.env.YIELD_REPORT_WORKSPACE)
    : path.resolve(process.cwd(), "..", "..");
}

export function conversationsDir() {
  return path.join(workspaceRoot(), ".agent_workbench", "conversations");
}

export function createConversation(title = "新会话"): ConversationRecord {
  const now = new Date().toISOString();
  return {
    id: randomUUID(),
    title,
    createdAt: now,
    updatedAt: now,
    latestStatus: "idle",
    messages: [],
    runIds: [],
  };
}

export async function listConversations(): Promise<ConversationSummary[]> {
  await mkdir(conversationsDir(), { recursive: true });
  const names = await readdir(conversationsDir());
  const records = await Promise.all(
    names
      .filter((name) => name.endsWith(".json"))
      .map(async (name) => readConversation(name.replace(/\.json$/, "")).catch(() => null)),
  );
  return records
    .filter((record): record is ConversationRecord => Boolean(record))
    .map(toSummary)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function readConversation(id: string): Promise<ConversationRecord> {
  const safe = safeConversationId(id);
  const raw = await readFile(path.join(conversationsDir(), `${safe}.json`), "utf-8");
  return normalizeConversation(JSON.parse(raw));
}

export async function saveConversation(record: ConversationRecord): Promise<ConversationRecord> {
  const normalized = normalizeConversation(record);
  await mkdir(conversationsDir(), { recursive: true });
  await writeFile(
    path.join(conversationsDir(), `${normalized.id}.json`),
    JSON.stringify(normalized, null, 2),
    "utf-8",
  );
  return normalized;
}

export function safeConversationId(id: string) {
  if (!/^[a-zA-Z0-9_-]{8,80}$/.test(id)) {
    throw new Error("Invalid conversation id");
  }
  return id;
}

export function normalizeConversation(value: unknown): ConversationRecord {
  if (!value || typeof value !== "object") {
    throw new Error("Conversation must be an object");
  }
  const data = value as Record<string, unknown>;
  const now = new Date().toISOString();
  const id = safeConversationId(String(data.id || randomUUID()));
  const messages = Array.isArray(data.messages)
    ? data.messages.map(normalizeMessage)
    : [];
  const runIds = Array.isArray(data.runIds)
    ? data.runIds.map((item) => String(item)).filter(Boolean)
    : [];
  return {
    id,
    title: String(data.title || messages.find((item) => item.role === "user")?.content || "新会话").slice(
      0,
      80,
    ),
    createdAt: String(data.createdAt || now),
    updatedAt: String(data.updatedAt || now),
    latestStatus: normalizeStatus(data.latestStatus),
    messages,
    runIds: Array.from(new Set(runIds)),
  };
}

function normalizeMessage(value: unknown): ConversationMessage {
  const data = (value || {}) as Record<string, unknown>;
  const role = data.role === "assistant" ? "assistant" : "user";
  return {
    id: String(data.id || randomUUID()),
    role,
    content: String(data.content || ""),
    body: typeof data.body === "string" ? data.body : undefined,
    status: data.status === "error" ? "error" : data.status === "success" ? "success" : undefined,
    warnings: Array.isArray(data.warnings) ? data.warnings.map(String) : [],
    artifacts: Array.isArray(data.artifacts) ? data.artifacts : [],
    createdAt: String(data.createdAt || new Date().toISOString()),
  };
}

function normalizeStatus(value: unknown): ConversationRecord["latestStatus"] {
  if (value === "running" || value === "completed" || value === "failed") {
    return value;
  }
  return "idle";
}

function toSummary(record: ConversationRecord): ConversationSummary {
  const last = record.messages.at(-1);
  return {
    id: record.id,
    title: record.title,
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
    latestStatus: record.latestStatus,
    runIds: record.runIds,
    messageCount: record.messages.length,
    lastMessage: last?.content || last?.body,
  };
}
