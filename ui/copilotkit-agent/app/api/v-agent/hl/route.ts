import fs from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST() {
  const messagePath = resolveLatestMessagePath();
  try {
    const message = await fs.readFile(messagePath, "utf8");
    return new NextResponse(formatHlMessageForGroup(message) || emptyMessage(), {
      status: 200,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  } catch (error) {
    const code = typeof error === "object" && error !== null && "code" in error ? error.code : "";
    if (code === "ENOENT") {
      return new NextResponse(emptyMessage(), {
        status: 200,
        headers: { "Content-Type": "text/plain; charset=utf-8" },
      });
    }
    const message = error instanceof Error ? error.message : String(error);
    return new NextResponse(`读取最新 HL 异常通报失败: ${message}`, {
      status: 500,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
}

function resolveLatestMessagePath() {
  if (process.env.YIELD_REPORT_V_AGENT_LATEST_MESSAGE_PATH) {
    return path.resolve(process.env.YIELD_REPORT_V_AGENT_LATEST_MESSAGE_PATH);
  }
  const workspace = process.env.YIELD_REPORT_WORKSPACE
    ? path.resolve(process.env.YIELD_REPORT_WORKSPACE)
    : path.resolve(process.cwd(), "..", "..");
  return path.join(workspace, "output", "latest_hl_anomaly_message.txt");
}

function emptyMessage() {
  return "暂无可推送的 HL 异常内容。请先在 Agent Workbench 点击异常HL/异常监控生成本地结果。";
}

function formatHlMessageForGroup(raw: string) {
  const lines = raw
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const sections: string[][] = [];
  let current: string[] = [];
  let insideHl = false;

  for (const line of lines) {
    if (/^---\s*HL\s+\d+/i.test(line)) {
      if (current.length) {
        sections.push(current);
        current = [];
      }
      insideHl = true;
      continue;
    }

    if (!insideHl && line.startsWith("【")) {
      insideHl = true;
    }
    if (!insideHl) {
      continue;
    }

    if (line.startsWith("【")) {
      current.push(line);
    } else if (current.length) {
      current[current.length - 1] = `${current[current.length - 1]} ${line}`;
    }
  }

  if (current.length) {
    sections.push(current);
  }

  if (!sections.length) {
    return raw.trim();
  }

  return sections.map((section) => section.join("\n\n")).join("\n\n");
}
